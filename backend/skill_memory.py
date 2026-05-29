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
import re
import uuid
from collections import Counter
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


# ═══════════════════════════════════════════════════════════════════════════════
#  RICHER MEMORY: outcome recording, prompt context, refinement patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Refinement phrase patterns we look for in user feedback. Each entry maps
# a short, actionable label to a regex that matches the underlying intent.
_REFINEMENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Sharper recommendations", re.compile(r"\b(sharper|sharpen|more actionable|specific recs?|specific recommendation)", re.I)),
    ("More patient voice", re.compile(r"\b(patient voice|patient quote|verbatim|in their own words|self[- ]report)", re.I)),
    ("Less generic phrasing", re.compile(r"\b(less generic|too generic|generic phrasing|boilerplate|less vague|sounds (generic|like ai))", re.I)),
    ("More evidence/quotes", re.compile(r"\b(more evidence|more quotes|cite (more|the)|back this up|need (a )?source)", re.I)),
    ("Tighter findings", re.compile(r"\b(tighter|tighten|more concise|shorten|less verbose|trim)", re.I)),
    ("More emotional nuance", re.compile(r"\b(emotional|emotion|sentiment nuance|how (they|patients) feel)", re.I)),
    ("Stronger headline framing", re.compile(r"\b(headline|punchier|stronger framing|reframe)", re.I)),
    ("Drop fluff/intros", re.compile(r"\b(no fluff|drop the intro|cut the preamble|skip the intro)", re.I)),
    ("Surface contradictions", re.compile(r"\b(contradict|tension|conflict|disagree|opposing)", re.I)),
    ("Quantify more", re.compile(r"\b(quantif|percentage|number|how many|stat(istic)?s?)", re.I)),
]


def _domain_hint_from_text(text: str) -> Optional[str]:
    """Best-effort: pull a disease/brand keyword out of free-form text."""
    if not text:
        return None
    # Look at common pharma / consumer keywords we've seen historically.
    keywords = [
        "hpp", "migraine", "oncology", "diabetes", "ms ", "multiple sclerosis",
        "alzheimer", "parkinson", "lupus", "psoriasis", "eczema", "asthma",
        "rare disease", "ultra-rare", "ultra rare", "pharma", "biotech",
        "cpg", "beauty", "skincare", "haircare", "fitness", "nutrition",
    ]
    lower = text.lower()
    for kw in keywords:
        if kw in lower:
            return kw.strip()
    return None


def record_run_outcome(session_id: str, outcome: dict) -> None:
    """After a run completes, record richer outcome data beyond preference counts.

    Captures:
    - What worked (high-confidence findings, themes that scored)
    - What was refined (user's feedback patterns)
    - How long it took (duration_seconds)
    - Provider/model used
    - Dataset characteristics (size, type, domain hint)

    This builds the memory more richly than just preference counts.
    """
    _ensure_dirs()
    prefs = _read_json(PREFERENCES_FILE, {
        "runs": [],
        "report_type_counts": {},
        "design_theme_counts": {},
        "provider_counts": {},
        "refinement_feedback": [],
        "outcomes": [],
        "dataset_domains": {},
        "durations_seconds": [],
        "findings_per_run": [],
    })

    prefs.setdefault("outcomes", [])
    prefs.setdefault("dataset_domains", {})
    prefs.setdefault("durations_seconds", [])
    prefs.setdefault("findings_per_run", [])
    prefs.setdefault("refinement_feedback", [])

    # ── Capture refinement feedback strings ──
    refinements = outcome.get("refinements") or []
    if isinstance(refinements, str):
        refinements = [refinements]
    for fb in refinements:
        if fb and isinstance(fb, str):
            prefs["refinement_feedback"].append({
                "session_id": session_id,
                "feedback": fb[:500],
                "timestamp": datetime.utcnow().isoformat(),
            })
    # Keep last 100 to bound size
    prefs["refinement_feedback"] = prefs["refinement_feedback"][-100:]

    # ── Duration ──
    duration = outcome.get("duration_seconds")
    if isinstance(duration, (int, float)) and duration > 0:
        prefs["durations_seconds"].append(float(duration))
        prefs["durations_seconds"] = prefs["durations_seconds"][-50:]

    # ── Findings count ──
    findings_count = outcome.get("findings_count")
    if isinstance(findings_count, int) and findings_count >= 0:
        prefs["findings_per_run"].append(findings_count)
        prefs["findings_per_run"] = prefs["findings_per_run"][-50:]

    # ── Dataset domain hint ──
    dataset = outcome.get("dataset") or {}
    domain = dataset.get("domain") or _domain_hint_from_text(
        " ".join([
            str(dataset.get("type", "")),
            str(outcome.get("additional_context", "")),
            str(outcome.get("user_prompt", "")),
        ])
    )
    if domain:
        prefs["dataset_domains"][domain] = prefs["dataset_domains"].get(domain, 0) + 1

    # ── Outcome record ──
    outcome_record = {
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "report_type": outcome.get("report_type", ""),
        "provider": outcome.get("provider", ""),
        "model": outcome.get("model", ""),
        "duration_seconds": duration,
        "findings_count": findings_count,
        "high_confidence_themes": (outcome.get("high_confidence_themes") or [])[:10],
        "dataset_size": dataset.get("row_count"),
        "dataset_type": dataset.get("type"),
        "dataset_domain": domain,
        "refinement_count": len(refinements),
    }
    prefs["outcomes"].append(outcome_record)
    prefs["outcomes"] = prefs["outcomes"][-50:]

    _write_json(PREFERENCES_FILE, prefs)
    log.info(f"Recorded run outcome for session {session_id[:8]}")


def extract_refinement_patterns() -> list[str]:
    """Analyze stored refinement feedback to extract common, actionable patterns.

    Returns a list of human-readable pattern labels (most frequent first), e.g.
        ["Sharper recommendations (4 times)", "More patient voice (3 times)"]
    """
    _ensure_dirs()
    prefs = _read_json(PREFERENCES_FILE, {})
    feedbacks = prefs.get("refinement_feedback", []) or []

    counter: Counter[str] = Counter()
    for entry in feedbacks:
        text = entry.get("feedback") if isinstance(entry, dict) else str(entry)
        if not text:
            continue
        for label, pattern in _REFINEMENT_PATTERNS:
            if pattern.search(text):
                counter[label] += 1

    return [f"{label} ({count} times)" for label, count in counter.most_common(8)]


def _format_counts(counts: dict, top_n: int = 3) -> str:
    if not counts:
        return ""
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return ", ".join(f"{k} ({v})" for k, v in ordered)


def get_memory_insights() -> dict:
    """Return a richer, structured snapshot of agent memory for the UI.

    Builds on get_learned_preferences() but adds derived insights useful for
    the Memory panel (refinement patterns, dataset domains, quality metrics).
    """
    _ensure_dirs()
    prefs = _read_json(PREFERENCES_FILE, {})
    base = get_learned_preferences()

    durations = prefs.get("durations_seconds", []) or []
    findings = prefs.get("findings_per_run", []) or []
    outcomes = prefs.get("outcomes", []) or []

    avg_duration = round(sum(durations) / len(durations), 1) if durations else None
    avg_findings = round(sum(findings) / len(findings), 1) if findings else None

    refinement_total = len(prefs.get("refinement_feedback", []) or [])
    refinement_per_run = (
        round(refinement_total / max(len(outcomes), 1), 2) if outcomes else 0
    )

    return {
        **base,
        "refinement_patterns": extract_refinement_patterns(),
        "dataset_domain_counts": prefs.get("dataset_domains", {}),
        "avg_duration_seconds": avg_duration,
        "avg_findings_per_report": avg_findings,
        "avg_refinements_per_run": refinement_per_run,
        "recent_outcomes": outcomes[-10:],
    }


def get_memory_context_for_prompt() -> str:
    """Return a formatted string for injection into the orchestrator's system prompt.

    Looks like:

        ## Past Run Memory

        Based on Emanuel's previous 14 runs:
        - Preferred report type for pharma data: pharma_social_intelligence
        - Preferred provider: openai (gpt-4o-mini for speed)
        - Common refinement requests: "more emphasis on patient voice", "sharper recommendations"
        - Past dataset patterns: HPP, migraine, oncology (ultra-rare diseases)
        - Average run length: 4.2 minutes

        When you start a new analysis, reference what you've learned. For example:
        "I notice you've run several pharma SI analyses before — I'll apply your typical
        framing: heavy on patient voice, sharp recommendations, no generic statements."

    If there is no memory yet, returns an empty string.
    """
    try:
        insights = get_memory_insights()
    except Exception as e:
        log.warning(f"get_memory_context_for_prompt failed: {e}")
        return ""

    total_runs = insights.get("total_runs", 0)
    if not total_runs:
        return ""

    lines: list[str] = ["## Past Run Memory", ""]
    lines.append(f"Based on Emanuel's previous {total_runs} runs:")

    pref_rt = insights.get("preferred_report_type")
    rt_counts = insights.get("report_type_counts") or {}
    if pref_rt:
        rt_extra = _format_counts(rt_counts, top_n=3)
        lines.append(f"- Preferred report type: {pref_rt}" + (f" (counts: {rt_extra})" if rt_extra else ""))

    pref_prov = insights.get("preferred_provider")
    prov_counts = insights.get("provider_counts") or {}
    if pref_prov:
        prov_extra = _format_counts(prov_counts, top_n=3)
        lines.append(f"- Preferred provider: {pref_prov}" + (f" (counts: {prov_extra})" if prov_extra else ""))

    pref_theme = insights.get("preferred_design_theme")
    if pref_theme:
        lines.append(f"- Preferred design theme: {pref_theme}")

    patterns = insights.get("refinement_patterns") or []
    if patterns:
        lines.append("- Common refinement requests: " + "; ".join(patterns[:5]))

    domain_counts = insights.get("dataset_domain_counts") or {}
    if domain_counts:
        domain_str = _format_counts(domain_counts, top_n=5)
        lines.append(f"- Past dataset patterns: {domain_str}")

    avg_dur = insights.get("avg_duration_seconds")
    if avg_dur:
        minutes = avg_dur / 60.0
        lines.append(f"- Average run length: {minutes:.1f} minutes")

    avg_findings = insights.get("avg_findings_per_report")
    if avg_findings is not None:
        lines.append(f"- Average findings per report: {avg_findings}")

    lines.extend([
        "",
        "When you start a new analysis, reference what you've learned in your thinking stream.",
        "Apply common refinement requests upfront — don't make the user ask twice.",
        'For example: "Based on Emanuel\'s past runs, I\'ll apply your typical framing — '
        'heavy on patient voice, sharper recommendations, no generic statements."',
        "",
        "When you do invoke a past pattern in your thinking, you may prefix that sentence",
        'with the marker `[memory]` so the UI can highlight it. Example:',
        '  [memory] Based on your past pharma SI runs, I\'m biasing toward patient-voice quotes.',
    ])

    return "\n".join(lines)


def reset_memory() -> dict:
    """Clear all learned preferences. Returns a summary of what was reset."""
    _ensure_dirs()
    prior = _read_json(PREFERENCES_FILE, {})
    prior_total = len(prior.get("runs", []) or [])
    empty = {
        "runs": [],
        "report_type_counts": {},
        "design_theme_counts": {},
        "provider_counts": {},
        "refinement_feedback": [],
        "outcomes": [],
        "dataset_domains": {},
        "durations_seconds": [],
        "findings_per_run": [],
    }
    _write_json(PREFERENCES_FILE, empty)
    log.info(f"Reset agent memory (cleared {prior_total} prior runs)")
    return {"ok": True, "cleared_runs": prior_total}
