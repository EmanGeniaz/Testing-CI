"""
Template Library — manages HTML report templates for the CI platform.

Templates define how analysis results are rendered into visual reports.
Includes a built-in storyboarded pharma template and supports user uploads.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("e_ai.template_library")

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))
TEMPLATES_DIR = DATA_DIR / "templates"


# ═══════════════════════════════════════════════════════════════════════════════
#  BUILT-IN TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

_BUILTIN_TEMPLATES: list[dict] = [
    {
        "id": "pharma_storyboard",
        "name": "Pharma Storyboard Report",
        "description": (
            "Cinematic, tabbed, interactive HTML intelligence report for "
            "pharma social intelligence data. Features hero sections, KPI "
            "flip cards, animated bars, verbatim evidence modals, and "
            "executive-friendly narrative flow."
        ),
        "builtin": True,
        "report_types": ["pharma_social_intelligence"],
        "tags": ["pharma", "storyboard", "interactive", "executive"],
        "renderer": "html_report_builder.build_pharma_html_report",
        "created_at": "2025-05-01T00:00:00Z",
    },
    {
        "id": "generic_executive",
        "name": "Executive Summary Template",
        "description": (
            "Clean executive summary layout suitable for any report type. "
            "Includes KPI tiles, findings list, evidence section, and "
            "recommendations."
        ),
        "builtin": True,
        "report_types": [
            "explainable_ai_tagging",
            "genz_brand_tracker",
            "pharma_social_intelligence",
        ],
        "tags": ["executive", "summary", "generic"],
        "renderer": "default",
        "created_at": "2025-05-01T00:00:00Z",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE LIBRARY CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class TemplateLibrary:
    """Manages built-in and uploaded HTML report templates."""

    def __init__(self, templates_dir: Path | None = None):
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    # ── List ──────────────────────────────────────────────────────────────────

    def list_templates(self) -> list[dict]:
        """List all available templates with metadata."""
        templates: list[dict] = []

        # Built-in templates
        for t in _BUILTIN_TEMPLATES:
            templates.append({**t})

        # Uploaded templates from disk
        meta_dir = self.templates_dir / "_meta"
        if meta_dir.exists():
            for fp in sorted(meta_dir.glob("*.json")):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta.setdefault("builtin", False)
                    templates.append(meta)
                except Exception as e:
                    log.warning(f"Failed to load template meta {fp}: {e}")

        return templates

    # ── Get ───────────────────────────────────────────────────────────────────

    def get_template(self, template_id: str) -> dict:
        """Get a template by ID. Returns metadata + html_content for uploads."""
        # Check built-in
        for t in _BUILTIN_TEMPLATES:
            if t["id"] == template_id:
                return {**t}

        # Check uploaded
        meta_path = self.templates_dir / "_meta" / f"{template_id}.json"
        html_path = self.templates_dir / f"{template_id}.html"

        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta.setdefault("builtin", False)
            if html_path.exists():
                with open(html_path, "r", encoding="utf-8") as f:
                    meta["html_content"] = f.read()
            return meta

        raise KeyError(f"Template '{template_id}' not found.")

    # ── Upload ────────────────────────────────────────────────────────────────

    def upload_template(
        self,
        name: str,
        html_content: str,
        metadata: dict | None = None,
    ) -> dict:
        """Save an uploaded HTML template."""
        metadata = metadata or {}

        # Generate ID
        template_id = metadata.get("id")
        if not template_id:
            slug = name.lower().replace(" ", "_").replace("-", "_")
            slug = "".join(c for c in slug if c.isalnum() or c == "_")
            template_id = f"{slug}_{uuid.uuid4().hex[:6]}"

        # Prevent overwriting built-in
        for t in _BUILTIN_TEMPLATES:
            if t["id"] == template_id:
                raise ValueError(
                    f"Cannot overwrite built-in template '{template_id}'."
                )

        # Build meta
        meta = {
            "id": template_id,
            "name": name,
            "description": metadata.get("description", ""),
            "builtin": False,
            "report_types": metadata.get("report_types", []),
            "tags": metadata.get("tags", []),
            "renderer": "uploaded",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        # Ensure dirs
        meta_dir = self.templates_dir / "_meta"
        meta_dir.mkdir(parents=True, exist_ok=True)

        # Write files
        meta_path = meta_dir / f"{template_id}.json"
        html_path = self.templates_dir / f"{template_id}.html"

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        log.info(f"Template uploaded: {template_id} → {html_path}")
        return meta

    # ── Match ─────────────────────────────────────────────────────────────────

    def match_template(
        self,
        report_type: str,
        dataset_context: dict | None = None,
    ) -> dict:
        """Pick the best template for a given report type and context."""
        dataset_context = dataset_context or {}
        all_templates = self.list_templates()

        # Score templates
        best: dict | None = None
        best_score = -1

        for t in all_templates:
            score = 0
            rt_list = t.get("report_types", [])

            # Exact report type match
            if report_type in rt_list:
                score += 10

            # Check if tags match any context keys
            tags = t.get("tags", [])
            for tag in tags:
                tag_lower = tag.lower()
                for key, val in dataset_context.items():
                    if isinstance(val, str) and tag_lower in val.lower():
                        score += 2

            if score > best_score:
                best_score = score
                best = t

        if best is not None:
            return best

        # Fallback: return generic if available
        for t in all_templates:
            if t["id"] == "generic_executive":
                return t

        # Last resort: first template
        if all_templates:
            return all_templates[0]

        return {
            "id": "none",
            "name": "No Template",
            "description": "No templates available.",
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_library: Optional[TemplateLibrary] = None


def get_template_library() -> TemplateLibrary:
    """Return the singleton TemplateLibrary instance."""
    global _library
    if _library is None:
        _library = TemplateLibrary()
    return _library
