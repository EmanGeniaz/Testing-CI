"""
Skill Registry — manages uploadable skill definitions for the CI platform.

Skills define how an agent should behave for a specific type of analysis.
They can be built-in (derived from existing report types) or uploaded as
JSON files by users.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from report_types import list_report_types

log = logging.getLogger("e_ai.skill_registry")

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))
SKILLS_DIR = DATA_DIR / "skills"


# ═══════════════════════════════════════════════════════════════════════════════
#  BUILT-IN SKILLS
# ═══════════════════════════════════════════════════════════════════════════════

_BUILTIN_SKILLS: list[dict] = [
    {
        "id": "explainable_ai_tagging",
        "name": "Explainable AI Tagging",
        "description": (
            "PR / reputation intelligence tagging with XAI rationale "
            "grounded in verbatim source text."
        ),
        "type": "report_type",
        "builtin": True,
        "trigger_words": [
            "PR", "reputation", "brand risk", "media intelligence",
            "XAI", "explainable", "tagging", "sentiment", "signals",
        ],
    },
    {
        "id": "pharma_social_intelligence",
        "name": "Pharma Social Intelligence",
        "description": (
            "Disease-area patient/caregiver insight tagging. Multi-finding "
            "output across Stage, Theme, Unmet Need, Concern, and QoL "
            "Impact dimensions."
        ),
        "type": "report_type",
        "builtin": True,
        "trigger_words": [
            "pharma", "pharmaceutical", "patient", "caregiver",
            "disease", "drug", "treatment", "HCP", "clinical",
            "health", "medical", "unmet need", "QoL",
        ],
    },
    {
        "id": "genz_brand_tracker",
        "name": "Gen Z Brand Tracker",
        "description": (
            "Brand social post tagging across 8 Gen Z value scores plus "
            "brand awareness, engagement, sentiment, influencer, comparison, "
            "and purchase/loyalty signals."
        ),
        "type": "report_type",
        "builtin": True,
        "trigger_words": [
            "Gen Z", "brand tracker", "brand awareness", "influencer",
            "loyalty", "engagement", "youth", "social media",
            "Nike", "Adidas", "purchase intent",
        ],
    },
    {
        "id": "storyboarding",
        "name": "Storyboard Intelligence",
        "description": (
            "Transforms tagged analysis data into a cinematic, storyboarded "
            "HTML intelligence report with hero sections, KPI flip cards, "
            "animated bars, verbatim evidence modals, and executive-friendly "
            "narrative flow."
        ),
        "type": "skill",
        "builtin": True,
        "trigger_words": [
            "storyboard", "report", "narrative", "storytelling",
            "HTML report", "executive", "presentation", "visual",
            "interactive", "cinematic",
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
#  SKILL REGISTRY CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class SkillRegistry:
    """Manages built-in and uploaded skills."""

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    # ── List ──────────────────────────────────────────────────────────────────

    def list_skills(self) -> list[dict]:
        """List all available skills (built-in + uploaded JSON files)."""
        skills: list[dict] = []

        # Built-in skills
        for s in _BUILTIN_SKILLS:
            skills.append({**s})

        # Uploaded skills from disk
        for fp in sorted(self.skills_dir.glob("*.json")):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Ensure required fields
                if "id" not in data:
                    data["id"] = fp.stem
                data.setdefault("builtin", False)
                data.setdefault("type", "uploaded")
                skills.append(data)
            except Exception as e:
                log.warning(f"Failed to load skill file {fp}: {e}")

        return skills

    # ── Get ───────────────────────────────────────────────────────────────────

    def get_skill(self, skill_id: str) -> dict:
        """Get a specific skill by ID."""
        # Check built-in first
        for s in _BUILTIN_SKILLS:
            if s["id"] == skill_id:
                return {**s}

        # Check uploaded files
        fp = self.skills_dir / f"{skill_id}.json"
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("id", skill_id)
            data.setdefault("builtin", False)
            data.setdefault("type", "uploaded")
            return data

        raise KeyError(f"Skill '{skill_id}' not found.")

    # ── Upload ────────────────────────────────────────────────────────────────

    def upload_skill(self, skill_data: dict) -> dict:
        """Save an uploaded skill JSON to the skills directory."""
        # Generate an ID if not provided
        skill_id = skill_data.get("id")
        if not skill_id:
            name = skill_data.get("name", "custom")
            slug = name.lower().replace(" ", "_").replace("-", "_")
            slug = "".join(c for c in slug if c.isalnum() or c == "_")
            skill_id = f"{slug}_{uuid.uuid4().hex[:6]}"
            skill_data["id"] = skill_id

        # Prevent overwriting built-in skills
        for s in _BUILTIN_SKILLS:
            if s["id"] == skill_id:
                raise ValueError(
                    f"Cannot overwrite built-in skill '{skill_id}'. "
                    "Choose a different ID."
                )

        skill_data.setdefault("builtin", False)
        skill_data.setdefault("type", "uploaded")
        skill_data.setdefault("trigger_words", [])

        fp = self.skills_dir / f"{skill_id}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(skill_data, f, indent=2, ensure_ascii=False)

        log.info(f"Skill uploaded: {skill_id} → {fp}")
        return skill_data

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_skill(self, skill_id: str) -> bool:
        """Delete an uploaded skill. Returns True if deleted, False if not found."""
        # Prevent deleting built-in skills
        for s in _BUILTIN_SKILLS:
            if s["id"] == skill_id:
                raise ValueError(f"Cannot delete built-in skill '{skill_id}'.")

        fp = self.skills_dir / f"{skill_id}.json"
        if fp.exists():
            fp.unlink()
            log.info(f"Skill deleted: {skill_id}")
            return True
        return False

    # ── Match ─────────────────────────────────────────────────────────────────

    def match_skill(self, prompt: str) -> list[dict]:
        """Given a user prompt, return skills ranked by keyword relevance."""
        prompt_lower = prompt.lower()
        prompt_words = set(prompt_lower.split())

        scored: list[tuple[float, dict]] = []

        for skill in self.list_skills():
            score = 0.0

            # Check name match
            name_lower = skill.get("name", "").lower()
            for word in name_lower.split():
                if word in prompt_lower:
                    score += 2.0

            # Check description match
            desc_lower = skill.get("description", "").lower()
            for word in prompt_words:
                if len(word) > 3 and word in desc_lower:
                    score += 1.0

            # Check trigger words
            trigger_words = skill.get("trigger_words", [])
            for tw in trigger_words:
                tw_lower = tw.lower()
                if tw_lower in prompt_lower:
                    score += 3.0
                elif any(w in prompt_lower for w in tw_lower.split()):
                    score += 1.0

            if score > 0:
                scored.append((score, skill))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored]


# ═══════════════════════════════════════════════════════════════════════════════
#  MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Return the singleton SkillRegistry instance."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
