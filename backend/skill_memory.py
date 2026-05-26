"""
Skill Memory — auto-learns from successful runs and stores user preferences.

After each successful orchestrator or tagging run, this module checks whether
the effective configuration was novel enough to save as a reusable skill.
It also accumulates user refinement preferences over time.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("e_ai.skill_memory")

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))
MEMORY_DIR = DATA_DIR / "memory"
PREFERENCES_FILE = MEMORY_DIR / "preferences.json"


def _ensure_dirs():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"Failed to read {path}: {e}")
        return default


def _write_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def save_run_as_skill(session_id: str, run_metadata: dict) -> Optional[dict]:
    """
    After a successful run, extract the effective configuration and save it
    as a new skill in the registry (if it's novel enough).

    Checks:
    - Was a custom schema used? If so, save it as a named skill
    - Was the prompt pattern novel? (not matching any existing skill)
    - Did the user refine the report? Save refinement preferences

    Returns the saved skill info or None if not novel enough.
    """
    _ensure_dirs()

    # Only process successful runs
    status = run_metadata.get("status", "")
    if status not in ("complete", "success"):
        return None

    # Check if a custom schema was used
    custom_schema = run_metadata.get("custom_schema")
    report_type = run_metadata.get("report_type", "")
    context = run_metadata.get("context", {})
    additional_context = context.get("additional_context", "")

    # Determine if this run is novel enough to save
    is_novel = False
    skill_name = ""
    skill_description = ""
    trigger_words: list[str] = []

    if custom_schema:
        # Custom schema was used -- always save it
        is_novel = True
        skill_name = custom_schema.get("description", "Custom Analysis")[:60]
        skill_description = (
            f"Auto-learned custom schema from session {session_id[:8]}. "
            f"Fields: {', '.join(f.get('name', '') for f in custom_schema.get('fields', []))}"
        )
        trigger_words = [f.get("name", "") for f in custom_schema.get("fields", []) if f.get("name")]

    elif report_type and report_type.startswith("custom_"):
        # Custom report type was created during the run
        is_novel = True
        skill_name = f"Learned: {report_type}"
        skill_description = f"Auto-learned configuration from session {session_id[:8]}"

    elif additional_context and len(additional_context) > 50:
        # Rich context was provided -- save as a contextual skill
        # Check if we already have a similar skill
        from skill_registry import get_skill_registry
        registry = get_skill_registry()
        existing = registry.match_skill(additional_context)
        # Only save if no good match exists
        if not existing or len(existing) == 0:
            is_novel = True
            # Extract a short name from the context
            first_sentence = additional_context.split(".")[0].strip()[:60]
            skill_name = f"Learned: {first_sentence}"
            skill_description = (
                f"Auto-learned from session {session_id[:8]}. "
                f"Context: {additional_context[:200]}"
            )
            # Extract potential trigger words from context
            words = additional_context.lower().split()
            # Keep words that are 4+ chars and not common stop words
            stop_words = {
                "that", "this", "with", "from", "they", "have", "been",
                "will", "more", "what", "when", "where", "which", "about",
                "their", "would", "could", "should", "these", "those",
                "than", "then", "some", "also", "into", "over", "your",
                "just", "like", "very", "much", "many", "each", "only",
            }
            trigger_words = list({
                w for w in words
                if len(w) >= 4 and w not in stop_words and w.isalpha()
            })[:10]

    if not is_novel:
        # Still record the run for preference learning
        _record_run_preferences(session_id, run_metadata)
        return None

    # Save as a new skill
    from skill_registry import get_skill_registry
    registry = get_skill_registry()

    skill_data = {
        "name": skill_name,
        "description": skill_description,
        "type": "learned",
        "trigger_words": trigger_words,
        "source_session": session_id,
        "source_report_type": report_type,
        "learned_at": datetime.utcnow().isoformat(),
    }

    if custom_schema:
        skill_data["custom_schema"] = custom_schema

    try:
        saved = registry.upload_skill(skill_data)
        log.info(f"Auto-learned skill from session {session_id[:8]}: {saved.get('id')}")
        # Also record preferences
        _record_run_preferences(session_id, run_metadata)
        return saved
    except Exception as e:
        log.warning(f"Failed to save learned skill: {e}")
        return None


def _record_run_preferences(session_id: str, run_metadata: dict):
    """Record run preferences for future recommendations."""
    _ensure_dirs()

    prefs = _read_json(PREFERENCES_FILE, {
        "runs": [],
        "report_type_counts": {},
        "design_theme_counts": {},
        "provider_counts": {},
        "refinement_feedback": [],
    })

    # Track report type usage
    report_type = run_metadata.get("report_type", "")
    if report_type:
        prefs["report_type_counts"][report_type] = (
            prefs["report_type_counts"].get(report_type, 0) + 1
        )

    # Track provider usage
    provider = run_metadata.get("provider", "")
    if provider:
        prefs["provider_counts"][provider] = (
            prefs["provider_counts"].get(provider, 0) + 1
        )

    # Track design theme if present
    design_theme = run_metadata.get("design_theme", "")
    if design_theme and design_theme != "default":
        prefs["design_theme_counts"][design_theme] = (
            prefs["design_theme_counts"].get(design_theme, 0) + 1
        )

    # Add to run history (keep last 50)
    prefs["runs"].append({
        "session_id": session_id,
        "report_type": report_type,
        "provider": provider,
        "timestamp": datetime.utcnow().isoformat(),
    })
    prefs["runs"] = prefs["runs"][-50:]

    _write_json(PREFERENCES_FILE, prefs)


def get_learned_preferences(user_id: str = "default") -> dict:
    """
    Return accumulated preferences from past runs:
    - Preferred report types per data type
    - Common refinement feedback patterns
    - Design theme preferences
    """
    _ensure_dirs()

    prefs = _read_json(PREFERENCES_FILE, {
        "runs": [],
        "report_type_counts": {},
        "design_theme_counts": {},
        "provider_counts": {},
        "refinement_feedback": [],
    })

    # Compute summaries
    total_runs = len(prefs.get("runs", []))

    # Preferred report type
    rt_counts = prefs.get("report_type_counts", {})
    preferred_report_type = (
        max(rt_counts, key=rt_counts.get) if rt_counts else None
    )

    # Preferred provider
    prov_counts = prefs.get("provider_counts", {})
    preferred_provider = (
        max(prov_counts, key=prov_counts.get) if prov_counts else None
    )

    # Preferred design theme
    dt_counts = prefs.get("design_theme_counts", {})
    preferred_design_theme = (
        max(dt_counts, key=dt_counts.get) if dt_counts else None
    )

    return {
        "total_runs": total_runs,
        "preferred_report_type": preferred_report_type,
        "preferred_provider": preferred_provider,
        "preferred_design_theme": preferred_design_theme,
        "report_type_counts": rt_counts,
        "provider_counts": prov_counts,
        "design_theme_counts": dt_counts,
        "refinement_feedback_count": len(prefs.get("refinement_feedback", [])),
    }
