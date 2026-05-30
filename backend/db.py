"""Database layer — Supabase Postgres with JSON-file fallback for local dev.

If SUPABASE_URL is not set, all functions delegate to the legacy JSON-file
storage exposed by ``main`` so existing local development keeps working.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from supabase_client import get_client, is_configured

SUPABASE_ENABLED = is_configured()


# ─────────────────────────────────────────────────────────────────────────────
#  Lazy import of the JSON-file fallback helpers so we avoid circular imports
# ─────────────────────────────────────────────────────────────────────────────
def _legacy():
    """Import main lazily to avoid circular import at module load time."""
    import importlib
    return importlib.import_module("main")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
#  Sessions
# ─────────────────────────────────────────────────────────────────────────────

def get_session(session_id: str, user_id: str) -> Optional[dict]:
    """Fetch a session, scoped to the user. Returns None when missing."""
    if not SUPABASE_ENABLED:
        m = _legacy()
        db = m.load_db()
        return db.get("sessions", {}).get(session_id)

    client = get_client()
    try:
        result = (
            client.table("sessions")
            .select("*")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception:
        return None
    if not result.data:
        return None

    row = result.data
    # Merge the jsonb 'data' blob with the top-level columns so callers see a
    # single flat session dict (mirrors the old JSON-file shape).
    blob = dict(row.get("data") or {})
    blob.setdefault("filename", row.get("filename"))
    blob.setdefault("agent_id", row.get("agent_id"))
    blob.setdefault("status", row.get("status"))
    blob["updated_at"] = row.get("updated_at")
    blob["id"] = row.get("id")
    return blob


def save_session(session_id: str, user_id: str, data: dict) -> None:
    """Upsert a session."""
    if not SUPABASE_ENABLED:
        m = _legacy()
        m.update_session(session_id, data)
        return

    client = get_client()
    record = {
        "id": session_id,
        "user_id": user_id,
        "filename": data.get("filename"),
        "agent_id": data.get("agent_id"),
        "status": data.get("status", "idle"),
        "data": data,
        "updated_at": _now_iso(),
    }
    client.table("sessions").upsert(record).execute()


def update_session(session_id: str, user_id: str, patch: dict) -> None:
    """Read-modify-write a session, scoped to the user."""
    existing = get_session(session_id, user_id) or {}
    existing.update(patch)
    save_session(session_id, user_id, existing)


def list_user_sessions(user_id: str) -> list[dict]:
    """List all sessions for a user (summary fields only)."""
    if not SUPABASE_ENABLED:
        m = _legacy()
        db = m.load_db()
        out = []
        for sid, s in db.get("sessions", {}).items():
            out.append({
                "id": sid,
                "filename": s.get("filename"),
                "agent_id": s.get("agent_id"),
                "status": s.get("status"),
                "updated_at": s.get("updated_at"),
            })
        out.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        return out

    client = get_client()
    result = (
        client.table("sessions")
        .select("id, filename, agent_id, status, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data or []


def delete_session(session_id: str, user_id: str) -> bool:
    if not SUPABASE_ENABLED:
        m = _legacy()
        db = m.load_db()
        if session_id in db.get("sessions", {}):
            del db["sessions"][session_id]
            m.save_db(db)
            return True
        return False

    client = get_client()
    client.table("sessions").delete().eq("id", session_id).eq("user_id", user_id).execute()
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  Runs
# ─────────────────────────────────────────────────────────────────────────────

def get_run(run_id: str, user_id: str) -> Optional[dict]:
    if not SUPABASE_ENABLED:
        m = _legacy()
        runs = m.load_runs().get("runs", [])
        for r in runs:
            if r.get("id") == run_id or r.get("run_id") == run_id:
                return r
        return None

    client = get_client()
    try:
        result = (
            client.table("runs")
            .select("*")
            .eq("id", run_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception:
        return None
    return result.data


def save_run(run_id: str, user_id: str, fields: dict) -> None:
    if not SUPABASE_ENABLED:
        m = _legacy()
        data = m.load_runs()
        runs = data.setdefault("runs", [])
        for i, r in enumerate(runs):
            if r.get("id") == run_id or r.get("run_id") == run_id:
                runs[i] = {**r, **fields, "id": run_id}
                m.save_runs(data)
                return
        runs.append({"id": run_id, **fields})
        m.save_runs(data)
        return

    client = get_client()
    record = {
        "id": run_id,
        "user_id": user_id,
        "session_id": fields.get("session_id"),
        "provider": fields.get("provider"),
        "model": fields.get("model"),
        "total_rows": fields.get("total_rows"),
        "completed": fields.get("completed", 0),
        "status": fields.get("status", "pending"),
        "started_at": fields.get("started_at"),
        "completed_at": fields.get("completed_at"),
        "data": fields.get("data", {}),
    }
    record = {k: v for k, v in record.items() if v is not None or k in ("data",)}
    client.table("runs").upsert(record).execute()


def list_user_runs(user_id: str) -> list[dict]:
    if not SUPABASE_ENABLED:
        m = _legacy()
        return m.load_runs().get("runs", [])

    client = get_client()
    result = (
        client.table("runs")
        .select("*")
        .eq("user_id", user_id)
        .order("started_at", desc=True)
        .execute()
    )
    return result.data or []


# ─────────────────────────────────────────────────────────────────────────────
#  User memory
# ─────────────────────────────────────────────────────────────────────────────

def get_user_memory(user_id: str) -> dict:
    if not SUPABASE_ENABLED:
        # Fallback uses skill_memory if available, otherwise empty dict
        try:
            from pathlib import Path
            import json
            m = _legacy()
            path = m.DATA_DIR / "user_memory.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    client = get_client()
    try:
        result = client.table("user_memory").select("data").eq("user_id", user_id).single().execute()
    except Exception:
        return {}
    if not result.data:
        return {}
    return result.data.get("data") or {}


def save_user_memory(user_id: str, data: dict) -> None:
    if not SUPABASE_ENABLED:
        try:
            import json
            m = _legacy()
            path = m.DATA_DIR / "user_memory.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass
        return

    client = get_client()
    record = {"user_id": user_id, "data": data, "updated_at": _now_iso()}
    client.table("user_memory").upsert(record).execute()


# ─────────────────────────────────────────────────────────────────────────────
#  MCP connector configs
# ─────────────────────────────────────────────────────────────────────────────

def get_mcp_configs(user_id: str) -> list[dict]:
    if not SUPABASE_ENABLED:
        try:
            import json
            m = _legacy()
            path = m.DATA_DIR / "mcp_configs.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    client = get_client()
    result = client.table("mcp_configs").select("*").eq("user_id", user_id).execute()
    return result.data or []


def save_mcp_config(user_id: str, connector_id: str, enabled: bool, config: dict) -> None:
    if not SUPABASE_ENABLED:
        try:
            import json
            m = _legacy()
            path = m.DATA_DIR / "mcp_configs.json"
            existing: list[dict] = []
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            updated = False
            for c in existing:
                if c.get("connector_id") == connector_id:
                    c["enabled"] = enabled
                    c["config"] = config
                    updated = True
                    break
            if not updated:
                existing.append({
                    "user_id": user_id,
                    "connector_id": connector_id,
                    "enabled": enabled,
                    "config": config,
                })
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, default=str)
        except Exception:
            pass
        return

    client = get_client()
    record = {
        "user_id": user_id,
        "connector_id": connector_id,
        "enabled": enabled,
        "config": config,
    }
    client.table("mcp_configs").upsert(record).execute()


# ─────────────────────────────────────────────────────────────────────────────
#  Share links
# ─────────────────────────────────────────────────────────────────────────────

def create_share_link(session_id: str, user_id: str, expires_in_days: int = 30) -> str:
    """Create a share link token and return it."""
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()

    if not SUPABASE_ENABLED:
        try:
            import json
            m = _legacy()
            path = m.DATA_DIR / "share_links.json"
            existing: dict = {}
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            token = secrets.token_hex(16)
            existing[token] = {
                "session_id": session_id,
                "user_id": user_id,
                "expires_at": expires_at,
                "created_at": _now_iso(),
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, default=str)
            return token
        except Exception:
            return ""

    client = get_client()
    token = secrets.token_hex(16)
    record = {
        "token": token,
        "session_id": session_id,
        "user_id": user_id,
        "expires_at": expires_at,
    }
    client.table("share_links").insert(record).execute()
    return token


def get_session_from_share_link(token: str) -> Optional[dict]:
    """Look up a share link, validate expiry, and return the underlying session."""
    if not SUPABASE_ENABLED:
        try:
            import json
            m = _legacy()
            path = m.DATA_DIR / "share_links.json"
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                links = json.load(f)
            link = links.get(token)
            if not link:
                return None
            if link.get("expires_at"):
                try:
                    if datetime.fromisoformat(link["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                        return None
                except Exception:
                    pass
            return get_session(link["session_id"], link["user_id"])
        except Exception:
            return None

    client = get_client()
    try:
        result = client.table("share_links").select("*").eq("token", token).single().execute()
    except Exception:
        return None
    if not result.data:
        return None
    link = result.data
    if link.get("expires_at"):
        try:
            if datetime.fromisoformat(link["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                return None
        except Exception:
            pass
    return get_session(link["session_id"], link["user_id"])
