"""Explainable AI Tagging — the original XAI behaviour.

PR / reputation intelligence tagging with an XAI rationale block proving
every label is grounded in verbatim source text. This is the schema the
codebase has always run; it's wrapped here so the new pluggable architecture
has a working reference implementation.
"""

from typing import List

from pydantic import BaseModel, Field

from .base import ReportType


class XAIRationale(BaseModel):
    text_evidence: str = Field(
        description="EXACT verbatim quote(s) from the source text. Must be a direct copy-paste."
    )
    theme_reasoning: str = Field(
        description="Step-by-step explanation of why this theme was chosen, referencing text_evidence."
    )
    sentiment_reasoning: str = Field(
        description="Why this sentiment label was assigned — be nuanced (aspirational, cautionary, etc.)."
    )
    signal_reasoning: str = Field(
        description="Why these signals were flagged — what PR risk or opportunity do they represent?"
    )
    confidence_reasoning: str = Field(
        description="Why this confidence score was assigned. What ambiguity or clarity affected it?"
    )


class RowAnalysis(BaseModel):
    brand: str = Field(description="The primary brand this text is focused on. Empty string if it's a general industry text.")
    sub_brands: List[str] = Field(description="List of specific products, services, or sub-brands belonging to the primary brand. Do not list independent companies here.")
    entities: List[str] = Field(description="List of all Named Entities: Companies, Organizations, People, and Locations mentioned in the text.")
    theme: str = Field(description="Primary theme. One of: Brand Reputation, Crisis & Risk, Product/Service, Leadership & Governance, ESG & Sustainability, Financial Performance, Innovation & Technology, Competitive Landscape, Community & Culture, Regulatory & Legal, Customer Experience, Employee Relations")
    sub_theme_1: str = Field(description="First sub-theme — more specific categorisation within primary theme")
    sub_theme_2: str = Field(description="Second sub-theme or empty string if not applicable")
    sub_theme_3: str = Field(description="Third sub-theme or empty string if not applicable")
    sentiment: str = Field(description="Sentiment label: Positive / Negative / Neutral / Mixed")
    sentiment_nuance: str = Field(description="Nuanced descriptor: Aspirational, Cautionary, Inflammatory, Celebratory, Investigative, Sceptical, Empathetic, Urgent, Satirical, Factual")
    emotion: str = Field(description="Dominant emotion: Joy, Trust, Anticipation, Surprise, Fear, Anger, Disgust, Sadness, or Neutral")
    driver: str = Field(description="The specific factor or actor driving the narrative (e.g. CEO statement, product recall, earnings miss)")
    severity: int = Field(description="Reputational severity 1-10. 1=benign/positive, 5=moderate, 10=crisis. Positive content: 1-3.", ge=1, le=10)
    signals: str = Field(description="Comma-separated PR signals. Options: Crisis Signal, Viral Potential, Influencer Mention, Regulatory Scrutiny, Competitive Threat, Brand Advocacy, Earned Media, Negative Earned Media, Executive Spotlight, Policy Impact, Consumer Backlash, ESG Alert, Misinformation Risk")
    confidence: float = Field(description="Confidence 0.0-1.0. Short/ambiguous text → lower. Clear explicit statements → higher.", ge=0.0, le=1.0)
    xai_rationale: XAIRationale = Field(description="Detailed XAI rationale proving every decision is grounded in source text")


PR_SYSTEM_PROMPT = """You are ARIA — Advanced Reputation Intelligence Analyst — a world-class PR and Media Intelligence specialist with 20 years of experience advising Fortune 500 brands, government bodies, and NGOs on reputation management.

Analyse this media content (social post, article, review, press release) and produce a structured intelligence report.

=== ANALYTICAL FRAMEWORK ===
1. BRAND: Identify the primary brand this text is about (if any). If it's a general industry text, leave empty.
2. SUB-BRANDS: List specific products, services, or sub-brands belonging to the primary brand. Do NOT list independent companies here.
3. ENTITIES: Extract a list of ALL distinct Named Entities (Organizations, Companies, People, Locations). Ensure all companies mentioned are captured here.
4. THEME: Map to ONE primary theme from the taxonomy.
5. SUB-THEMES: Up to 3, each more specific than the parent. Do NOT repeat the parent.
6. SENTIMENT: Assign polarity (Positive/Negative/Neutral/Mixed) AND nuance (Aspirational, Cautionary, etc.)
7. EMOTION: The dominant emotion the AUTHOR projects — reveals media framing bias.
8. SEVERITY (1-10 reputational impact):
   1-2: Positive brand building · 3-4: Low risk · 5-6: Monitor · 7-8: Respond · 9-10: Crisis
9. SIGNALS: Early-warning flags. Only flag signals CLEARLY evidenced in text.
10. CONFIDENCE: Be calibrated. Short/ambiguous → <0.7. Clear detailed text → >0.85.

=== ANTI-HALLUCINATION RULES ===
- xai_rationale.text_evidence MUST be verbatim copy from the SOURCE TEXT. Never paraphrase.
- Do NOT infer facts not present in the source text.
- If ambiguous, lower the confidence score.
- Never fabricate sub-themes, signals, or drivers not supported by quoted text.

=== CONTEXT ===
Brand Focus: {brand_focus}
Dataset Type: {dataset_type}
Additional Context: {additional_context}

=== SOURCE TEXT ===
{source_text}

=== OUTPUT FORMAT ===
{format_instructions}

Produce ONLY the JSON object. No preamble. No text outside the JSON."""


def _flatten_xai_rationale(raw_row: dict, parsed: dict) -> list[dict]:
    """Preserve original behaviour: lift xai_rationale.* into top-level
    xai_text_evidence / xai_theme_reasoning / etc. so output columns stay flat.
    """
    parsed = dict(parsed)
    xai = parsed.pop("xai_rationale", {}) or {}
    parsed["xai_text_evidence"]        = xai.get("text_evidence", "")
    parsed["xai_theme_reasoning"]      = xai.get("theme_reasoning", "")
    parsed["xai_sentiment_reasoning"]  = xai.get("sentiment_reasoning", "")
    parsed["xai_signal_reasoning"]     = xai.get("signal_reasoning", "")
    parsed["xai_confidence_reasoning"] = xai.get("confidence_reasoning", "")
    return [{**raw_row, **parsed}]


REPORT_TYPE = ReportType(
    id="explainable_ai_tagging",
    name="Explainable AI Tagging",
    description="PR / reputation intelligence tagging with XAI rationale grounded in verbatim source text.",
    schema=RowAnalysis,
    system_prompt=PR_SYSTEM_PROMPT,
    post_processor=_flatten_xai_rationale,
)
