"""Snapshot persistence for session and run state.

Render's free tier wipes the data directory on every redeploy/restart, so we
periodically dump the entire in-memory/disk state to a single combined JSON
snapshot file. The snapshot can live alongside the regular database files —
when the server restarts we attempt to reload it before serving requests.

The snapshot is intentionally one file (vs. many): a single file is easier to
back up to external storage (S3, git, etc.) and survives even partial wipes
better than a directory tree.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("e_ai.snapshot")

SNAPSHOT_FILENAME = "snapshot.json"
SNAPSHOT_VERSION = 1


# ── Path resolution ───────────────────────────────────────────────────────────

def resolve_data_dir() -> Path:
    """Pick the best writable data directory, in priority order.

    1. $DATA_DIR if explicitly set and writable.
    2. /opt/render/project/data — Render's persistent disk mount.
    3. /tmp/ci-agent-data — always writable, ephemeral (survives within a run).
    4. <backend dir> — fallback for local development.

    The first writable candidate wins. We always `mkdir -p` and probe the dir
    with a real write to make sure it actually accepts files (some platforms
    expose a path that mkdir succeeds on but writes fail).
    """
    candidates: list[Path] = []

    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    candidates.extend([
        Path("/opt/render/project/data"),
        Path("/tmp/ci-agent-data"),
        Path(__file__).resolve().parent,
    ])

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            log.info(f"DATA_DIR resolved to: {candidate}")
            return candidate
        except OSError as e:
            log.warning(f"DATA_DIR candidate {candidate} not writable: {e}")
            continue

    # Absolute last resort — return CWD; the caller will likely crash, but at
    # least we surface a useful error.
    fallback = Path.cwd()
    log.error(f"No writable DATA_DIR candidate found; falling back to {fallback}")
    return fallback


# ── Snapshot save / load ──────────────────────────────────────────────────────

def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write JSON atomically — write to .tmp, then rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    tmp.replace(path)


def save_snapshot(
    data_dir: Path,
    db_path: Path,
    runs_path: Path,
    runs_dir: Path,
) -> Optional[Path]:
    """Dump the full DB + run index + per-run files to a single JSON snapshot.

    Returns the snapshot path on success, None on failure (failures are logged
    but never raised — snapshotting must never break the request path).
    """
    try:
        snapshot_path = data_dir / SNAPSHOT_FILENAME

        sessions: dict = {}
        if db_path.exists():
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
            except Exception as e:
                log.warning(f"snapshot: could not read {db_path}: {e}")
                sessions = {"sessions": {}}

        runs_index: dict = {"runs": []}
        if runs_path.exists():
            try:
                with open(runs_path, "r", encoding="utf-8") as f:
                    runs_index = json.load(f)
            except Exception as e:
                log.warning(f"snapshot: could not read {runs_path}: {e}")

        per_run: dict = {}
        if runs_dir.exists() and runs_dir.is_dir():
            for run_file in runs_dir.glob("*.json"):
                try:
                    with open(run_file, "r", encoding="utf-8") as f:
                        per_run[run_file.stem] = json.load(f)
                except Exception as e:
                    log.warning(f"snapshot: could not read run file {run_file}: {e}")

        payload = {
            "version": SNAPSHOT_VERSION,
            "saved_at": datetime.utcnow().isoformat(),
            "db": sessions,
            "runs_index": runs_index,
            "runs": per_run,
        }

        _atomic_write_json(snapshot_path, payload)
        log.info(
            f"Snapshot saved: {snapshot_path} "
            f"({len(sessions.get('sessions', {}))} sessions, "
            f"{len(runs_index.get('runs', []))} runs, "
            f"{len(per_run)} run files)"
        )
        return snapshot_path
    except Exception as e:
        log.error(f"save_snapshot failed: {e}")
        return None


def load_snapshot(
    data_dir: Path,
    db_path: Path,
    runs_path: Path,
    runs_dir: Path,
    *,
    force: bool = False,
) -> bool:
    """Restore DB + runs from a snapshot file if one exists.

    If `force` is False (default), we only restore data when the target files
    don't already exist or are empty — i.e. fresh-restart recovery. If `force`
    is True we overwrite. Returns True iff anything was restored.
    """
    snapshot_path = data_dir / SNAPSHOT_FILENAME
    if not snapshot_path.exists():
        log.info(f"No snapshot found at {snapshot_path} — starting fresh")
        return False

    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        log.error(f"load_snapshot: could not parse {snapshot_path}: {e}")
        return False

    version = payload.get("version")
    if version != SNAPSHOT_VERSION:
        log.warning(f"Snapshot version mismatch (found {version}, expected {SNAPSHOT_VERSION}) — attempting load anyway")

    restored = False

    db_payload = payload.get("db") or {"sessions": {}}
    if force or not db_path.exists() or db_path.stat().st_size == 0:
        try:
            _atomic_write_json(db_path, db_payload)
            restored = True
            log.info(
                f"Restored DB from snapshot: {len(db_payload.get('sessions', {}))} sessions"
            )
        except Exception as e:
            log.error(f"Failed to restore DB: {e}")

    runs_index_payload = payload.get("runs_index") or {"runs": []}
    if force or not runs_path.exists() or runs_path.stat().st_size == 0:
        try:
            _atomic_write_json(runs_path, runs_index_payload)
            restored = True
            log.info(
                f"Restored runs index from snapshot: {len(runs_index_payload.get('runs', []))} runs"
            )
        except Exception as e:
            log.error(f"Failed to restore runs index: {e}")

    per_run = payload.get("runs") or {}
    if per_run:
        try:
            runs_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.error(f"Failed to create runs dir {runs_dir}: {e}")
            return restored

        restored_runs = 0
        for run_id, run_data in per_run.items():
            target = runs_dir / f"{run_id}.json"
            if not force and target.exists() and target.stat().st_size > 0:
                continue
            try:
                _atomic_write_json(target, run_data)
                restored_runs += 1
            except Exception as e:
                log.warning(f"Failed to restore run {run_id}: {e}")
        if restored_runs:
            restored = True
            log.info(f"Restored {restored_runs} run files from snapshot")

    saved_at = payload.get("saved_at", "unknown")
    log.info(f"Snapshot load complete (saved_at={saved_at}, restored={restored})")
    return restored


def snapshot_status(data_dir: Path) -> dict:
    """Return a tiny status blob describing the on-disk snapshot."""
    snapshot_path = data_dir / SNAPSHOT_FILENAME
    if not snapshot_path.exists():
        return {"exists": False, "path": str(snapshot_path)}
    try:
        stat = snapshot_path.stat()
        with open(snapshot_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return {
            "exists": True,
            "path": str(snapshot_path),
            "size_bytes": stat.st_size,
            "saved_at": payload.get("saved_at"),
            "session_count": len((payload.get("db") or {}).get("sessions", {})),
            "run_count": len((payload.get("runs_index") or {}).get("runs", [])),
        }
    except Exception as e:
        return {"exists": True, "path": str(snapshot_path), "error": str(e)}
