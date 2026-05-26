"""
Design skill connector -- interface for Canva, Claude Design, and other design tools.
Currently a placeholder with the interface defined. Actual Canva API integration
will be added when the MCP connector is available.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger("e_ai.design_connector")


# ═══════════════════════════════════════════════════════════════════════════════
#  COLOR THEMES
# ═══════════════════════════════════════════════════════════════════════════════

THEMES: dict[str, dict[str, str]] = {
    "corporate_blue": {
        "--brand-1": "#2563EB",
        "--brand-2": "#3B82F6",
        "--brand-3": "#60A5FA",
        "--brand-bg": "#EFF6FF",
        "--brand-text": "#1E3A5F",
    },
    "pharma_green": {
        "--brand-1": "#059669",
        "--brand-2": "#10B981",
        "--brand-3": "#34D399",
        "--brand-bg": "#ECFDF5",
        "--brand-text": "#064E3B",
    },
    "bold_pink": {
        "--brand-1": "#DB2777",
        "--brand-2": "#EC4899",
        "--brand-3": "#F472B6",
        "--brand-bg": "#FDF2F8",
        "--brand-text": "#831843",
    },
    "neutral_gray": {
        "--brand-1": "#4B5563",
        "--brand-2": "#6B7280",
        "--brand-3": "#9CA3AF",
        "--brand-bg": "#F9FAFB",
        "--brand-text": "#1F2937",
    },
}


class DesignConnector:
    """Interface for applying design themes and brand styling to reports."""

    def __init__(self):
        self.available_tools = [
            {
                "id": "canva",
                "name": "Canva",
                "status": "coming_soon",
                "capabilities": [
                    "brand_templates",
                    "color_palettes",
                    "hero_banners",
                    "social_cards",
                ],
            },
            {
                "id": "claude_design",
                "name": "Claude Design",
                "status": "active",
                "capabilities": [
                    "html_styling",
                    "css_themes",
                    "color_adjustment",
                    "layout_refinement",
                ],
            },
        ]

    def list_tools(self) -> list[dict]:
        """Return the list of available design tools and their status."""
        return self.available_tools

    def apply_brand_theme(self, html_content: str, brand_config: dict) -> str:
        """
        Apply brand colors, fonts, and styling to an HTML report.

        brand_config: {
            "primary_color": "#5B2EFF",
            "secondary_color": "#FF4D8D",
            "font_heading": "Sora",
            "font_body": "Plus Jakarta Sans",
            "logo_text": "InfoVision",
        }
        """
        primary = brand_config.get("primary_color", "#5B2EFF")
        secondary = brand_config.get("secondary_color", "#FF4D8D")
        font_heading = brand_config.get("font_heading", "Sora")
        font_body = brand_config.get("font_body", "Plus Jakarta Sans")
        logo_text = brand_config.get("logo_text", "")

        # Build a CSS override block
        css_override = f"""
<style>
  :root {{
    --brand-primary: {primary};
    --brand-secondary: {secondary};
    --font-heading: '{font_heading}', sans-serif;
    --font-body: '{font_body}', sans-serif;
  }}
  body {{ font-family: var(--font-body); }}
  h1, h2, h3, h4, h5, h6 {{ font-family: var(--font-heading); }}
  .gradient-text {{
    background: linear-gradient(135deg, {primary}, {secondary});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .hero-section {{
    background: linear-gradient(135deg, {primary}15, {secondary}10);
  }}
  .kpi-card:hover {{
    border-color: {primary};
    box-shadow: 0 4px 20px {primary}25;
  }}
  .accent-bar {{
    background: linear-gradient(90deg, {primary}, {secondary});
  }}
</style>
"""
        # Inject CSS before </head> if present, else prepend
        if "</head>" in html_content:
            html_content = html_content.replace("</head>", f"{css_override}\n</head>")
        else:
            html_content = css_override + html_content

        # Replace logo text if specified
        if logo_text:
            html_content = html_content.replace(
                "InfoVision", logo_text
            )

        log.info(f"Applied brand theme: primary={primary}, secondary={secondary}")
        return html_content

    def generate_hero_banner(
        self,
        title: str,
        subtitle: str,
        brand_config: dict,
    ) -> str:
        """Generate a hero banner HTML. Future: use Canva API."""
        primary = brand_config.get("primary_color", "#5B2EFF")
        secondary = brand_config.get("secondary_color", "#FF4D8D")
        font_heading = brand_config.get("font_heading", "Sora")

        return f"""
<div style="
  background: linear-gradient(135deg, {primary}12, {secondary}08);
  border-left: 4px solid {primary};
  padding: 48px 40px;
  margin-bottom: 32px;
  border-radius: 12px;
">
  <h1 style="
    font-family: '{font_heading}', sans-serif;
    font-size: 42px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0 0 12px 0;
    line-height: 1.1;
  ">{title}</h1>
  <p style="
    font-size: 18px;
    color: #64748b;
    margin: 0;
    line-height: 1.5;
  ">{subtitle}</p>
</div>
"""

    def adjust_color_theme(self, html_content: str, theme: str) -> str:
        """
        Apply a named color theme to the report.
        Themes: corporate_blue, pharma_green, bold_pink, neutral_gray, custom
        """
        theme_vars = THEMES.get(theme)
        if not theme_vars:
            log.warning(f"Unknown theme '{theme}', returning content unchanged")
            return html_content

        # Build CSS variable declarations
        css_vars = "\n    ".join(f"{k}: {v};" for k, v in theme_vars.items())
        css_block = f"""
<style>
  :root {{
    {css_vars}
  }}
  /* Theme: {theme} */
  .hero-section, .report-header {{
    background: linear-gradient(135deg, {theme_vars['--brand-1']}12, {theme_vars['--brand-2']}08) !important;
    border-left-color: {theme_vars['--brand-1']} !important;
  }}
  .gradient-text, .accent-text {{
    background: linear-gradient(135deg, {theme_vars['--brand-1']}, {theme_vars['--brand-2']}) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
  }}
  .accent-bar, .progress-bar {{
    background: linear-gradient(90deg, {theme_vars['--brand-1']}, {theme_vars['--brand-2']}) !important;
  }}
  .kpi-card:hover, .finding-card:hover {{
    border-color: {theme_vars['--brand-1']} !important;
    box-shadow: 0 4px 20px {theme_vars['--brand-1']}25 !important;
  }}
  .tag, .badge {{
    background: {theme_vars['--brand-bg']} !important;
    color: {theme_vars['--brand-1']} !important;
  }}
</style>
"""
        # Inject the CSS
        if "</head>" in html_content:
            html_content = html_content.replace("</head>", f"{css_block}\n</head>")
        elif "<body" in html_content:
            html_content = html_content.replace(
                "<body", f"{css_block}\n<body"
            )
        else:
            html_content = css_block + html_content

        log.info(f"Applied color theme: {theme}")
        return html_content


# ═══════════════════════════════════════════════════════════════════════════════
#  MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_connector: Optional[DesignConnector] = None


def get_design_connector() -> DesignConnector:
    """Return the singleton DesignConnector instance."""
    global _connector
    if _connector is None:
        _connector = DesignConnector()
    return _connector
