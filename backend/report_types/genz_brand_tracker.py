"""Gen Z Brand Tracker — AD's methodology.

Tags brand social posts across eight Gen Z value dimensions, brand awareness,
engagement, sentiment, influencer impact, competitive comparison, and
purchase/loyalty signals. 1:1 output (one input post → one tagged row).

Field set is reverse-engineered from the Nike/Adidas/Lululemon tagged
dataset (63 columns). About 50 of those are LLM-generated; the rest
(Original_Text, Likes/Shares/Comments, Source_Country, etc.) are input
metadata that the run loop carries through automatically.
"""

from typing import List

from pydantic import BaseModel, Field

from .base import ReportType


# ── Controlled vocabularies (from Nike/Adidas/Lululemon coded dataset) ───────

CONTENT_TYPES   = ["News", "Post", "TikTok", "Video"]
PLATFORMS       = ["Facebook", "Instagram", "LinkedIn", "Radio/Broadcast",
                   "Reddit", "TV/Broadcast", "TikTok", "X", "YouTube"]
MENTION_TYPES   = ["Campaign mention", "Direct mention",
                   "Logo / visual mention", "Product mention"]
REACH_PROXY     = ["High", "Medium", "Low"]
POPULARITY      = ["Viral", "Trending", "Frequently discussed",
                   "Niche", "Low visibility"]
ENGAGEMENT_RATE = ["Very high", "High", "Medium", "Low"]
ENGAGEMENT_DRIVERS = ["Community conversation", "Controversy", "Influencer post",
                     "Lifestyle aspiration", "Meme-humor", "News coverage",
                     "Product launch", "Promotion", "Trend participation"]
SENTIMENT       = ["Positive", "Neutral", "Negative"]
INFLUENCER_TYPES = ["Nano", "Micro", "Macro", "Mega", "Celebrity athlete",
                    "Celebrity non-athlete", "None"]
PARTNERSHIP_TYPES = ["Paid partnership", "Organic mention", "Ambassador",
                     "Unknown", "None"]
LOYALTY_IMPACT  = ["Strong positive", "Moderate positive", "Weak positive",
                   "Neutral", "Negative backlash"]
GENZ_ALIGNMENT  = ["Strong", "Moderate", "Weak", "None"]
PURCHASE_INTENT = ["Strong buy intent", "Moderate buy intent",
                   "Interest only", "No intent", "Avoidance"]
LOYALTY_LEVEL   = ["Loyal advocate", "Loyal customer", "Exploring",
                   "Switcher", "Competitor leaning", "Brand critic"]
ADVOCACY_LEVEL  = ["Defends brand", "Recommends", "Shares content",
                   "Passive", "Detracts"]


class GenZBrandAnalysis(BaseModel):
    """Single-finding tag set for one brand social post."""

    # ── Content classification ─────────────────────────────────────────
    detected_language: str = Field(default="English", description="Language detected, default English.")
    content_type: str = Field(description=f"Content format. One of: {', '.join(CONTENT_TYPES)}.")

    # ── Brand awareness ────────────────────────────────────────────────
    primary_brand: str = Field(description="The main brand the post is about. Use the canonical brand name. 'Multiple' if no single brand dominates.")
    secondary_brand: str = Field(default="", description="Other brand mentioned, if any. Comma-separated for multiple. Empty if none.")
    brand_mention_type: str = Field(description=f"How the brand is mentioned. One of: {', '.join(MENTION_TYPES)}.")
    brand_reach_proxy: str = Field(description=f"Inferred reach. One of: {', '.join(REACH_PROXY)}.")
    popularity_signal: str = Field(description=f"Popularity level. One of: {', '.join(POPULARITY)}.")
    brand_awareness_tagging_logic: str = Field(description="One-sentence rationale for the brand awareness tags, grounded in the post.")
    brand_awareness_confidence: int = Field(ge=0, le=100, description="Confidence 0-100.")

    # ── Engagement ─────────────────────────────────────────────────────
    engagement_rate_class: str = Field(description=f"Inferred engagement level. One of: {', '.join(ENGAGEMENT_RATE)}.")
    engagement_driver: str = Field(description=f"Primary driver of engagement. One of: {', '.join(ENGAGEMENT_DRIVERS)}.")
    engagement_tagging_logic: str = Field(description="One-sentence rationale for the engagement tags.")
    engagement_confidence: int = Field(ge=0, le=100, description="Confidence 0-100.")

    # ── Sentiment ──────────────────────────────────────────────────────
    sentiment: str = Field(description=f"Polarity. One of: {', '.join(SENTIMENT)}.")
    sentiment_intensity: int = Field(ge=1, le=5, description="Intensity 1 (mild) to 5 (extreme).")
    emotion: str = Field(description="Dominant emotion(s). Free text. Multiple comma-separated if blended (e.g. 'Excitement, Pride').")
    sentiment_driver: str = Field(description="Short phrase describing what's driving the sentiment.")
    sentiment_tagging_logic: str = Field(description="One-sentence rationale for sentiment, grounded in the post.")
    sentiment_confidence: int = Field(ge=0, le=100, description="Confidence 0-100.")

    # ── Influencer ─────────────────────────────────────────────────────
    influencer_mentioned: str = Field(description="'Yes' or 'No'.")
    influencer_name: str = Field(default="", description="Name(s) of influencer(s) mentioned. Empty if none.")
    influencer_type: str = Field(default="None", description=f"Type of influencer. One of: {', '.join(INFLUENCER_TYPES)}.")
    partnership_type: str = Field(default="None", description=f"Partnership nature. One of: {', '.join(PARTNERSHIP_TYPES)}.")
    influencer_impact_on_loyalty: str = Field(default="Neutral", description=f"Loyalty impact. One of: {', '.join(LOYALTY_IMPACT)}.")
    influencer_impact_logic: str = Field(default="", description="One-sentence rationale (empty if no influencer mentioned).")
    influencer_confidence: int = Field(ge=0, le=100, description="Confidence 0-100.")

    # ── Comparison ─────────────────────────────────────────────────────
    comparison_present: str = Field(description="'Yes' or 'No' — does the post compare brands?")
    compared_brands: str = Field(default="", description="Comma-separated brands compared. Empty if comparison_present='No'.")
    winner_perception: str = Field(default="Unclear", description="Which brand the post favors, or 'Unclear'. Empty if comparison_present='No'.")
    comparison_category: str = Field(default="", description="What axes are being compared (Comfort, Quality, Style, etc.). Comma-separated. Empty if none.")
    comparison_tagging_logic: str = Field(default="", description="One-sentence rationale (empty if no comparison).")
    comparison_confidence: int = Field(ge=0, le=100, description="Confidence 0-100.")

    # ── Gen Z values (each score 1-5) ──────────────────────────────────
    sustainability_score: int = Field(ge=1, le=5, description="How strongly the post reflects Gen Z sustainability values. 1=weak/absent, 5=strong.")
    inclusivity_score: int = Field(ge=1, le=5, description="Gen Z inclusivity/diversity values. 1-5.")
    authenticity_score: int = Field(ge=1, le=5, description="Authenticity/realness valued by Gen Z. 1-5.")
    community_score: int = Field(ge=1, le=5, description="Community-building value. 1-5.")
    wellness_score: int = Field(ge=1, le=5, description="Wellness/mental health value. 1-5.")
    individuality_score: int = Field(ge=1, le=5, description="Self-expression/individuality value. 1-5.")
    social_justice_alignment: int = Field(ge=1, le=5, description="Alignment with social justice causes. 1-5.")
    trend_relevance: int = Field(ge=1, le=5, description="How on-trend the content is for Gen Z right now. 1-5.")
    genz_values_alignment_level: str = Field(description=f"Overall Gen Z alignment. One of: {', '.join(GENZ_ALIGNMENT)}.")
    genz_values_tagging_logic: str = Field(description="One-sentence rationale tying the scores back to the post content.")
    genz_confidence: int = Field(ge=0, le=100, description="Confidence 0-100.")

    # ── Purchase / loyalty ─────────────────────────────────────────────
    purchase_intent: str = Field(description=f"Intent signal. One of: {', '.join(PURCHASE_INTENT)}.")
    repeat_purchase_intent: str = Field(description="'Yes', 'No', or 'Unknown'.")
    brand_loyalty_level: str = Field(description=f"Loyalty level. One of: {', '.join(LOYALTY_LEVEL)}.")
    advocacy_level: str = Field(description=f"Advocacy behavior. One of: {', '.join(ADVOCACY_LEVEL)}.")
    purchase_loyalty_logic: str = Field(description="One-sentence rationale for purchase/loyalty tags.")
    purchase_loyalty_confidence: int = Field(ge=0, le=100, description="Confidence 0-100.")


GENZ_SYSTEM_PROMPT = """You are a Gen Z Brand Intelligence analyst. You tag social media posts about consumer brands across eight Gen Z value dimensions plus brand awareness, engagement, sentiment, influencer impact, competitive comparison, and purchase/loyalty signals.

The audience for your output is a brand marketing team using this data to drive a Gen Z brand-tracking dashboard. Every tag must be defensible from the post content — no inferring beyond what's there.

=== BRAND CONTEXT ===
Brand focus: {brand_focus}
Dataset notes: {dataset_type}
Additional context: {additional_context}

=== TAGGING APPROACH ===

For each of the six tag groups, produce the listed fields plus a short
"tagging_logic" rationale (one sentence) and a numeric "confidence" (0-100).

1. CONTENT & BRAND AWARENESS
   - content_type, primary_brand, secondary_brand, brand_mention_type,
     brand_reach_proxy, popularity_signal
   - Use the controlled vocabularies in the schema descriptions.

2. ENGAGEMENT
   - engagement_rate_class, engagement_driver
   - Infer from cues in the post (virality language, comment activity hints,
     trend participation). Do not invent metrics.

3. SENTIMENT
   - sentiment (Pos/Neu/Neg), sentiment_intensity (1-5), emotion,
     sentiment_driver
   - emotion can be multi-valued (comma-separated) for blended emotional content.

4. INFLUENCER
   - If no influencer is mentioned, set influencer_mentioned="No" and leave
     influencer-specific fields at their defaults.

5. COMPARISON
   - If the post doesn't compare brands, set comparison_present="No" and leave
     comparison-specific fields at their defaults.

6. GEN Z VALUES (eight scores, 1-5 each)
   - sustainability, inclusivity, authenticity, community, wellness,
     individuality, social_justice_alignment, trend_relevance
   - Score 1 = absent or weak in this post. Score 5 = post centrally
     embodies this value. Most posts will have most scores at 1-2.
   - Then summarize with genz_values_alignment_level (Strong/Moderate/Weak/None).

7. PURCHASE & LOYALTY
   - purchase_intent, repeat_purchase_intent, brand_loyalty_level, advocacy_level
   - Infer from author behavior in the post. If unclear, choose the most
     neutral option in the vocabulary.

=== ANTI-HALLUCINATION RULES ===
- Do NOT invent brand mentions, influencers, or events not in the post.
- Confidence scores must be calibrated: short/ambiguous posts → 50-70,
  clear posts with explicit signals → 80-95.
- Tagging logic strings should reference specific cues from the post,
  not generic justifications.

=== SOURCE POST ===
{source_text}

=== OUTPUT FORMAT ===
{format_instructions}

Produce ONLY the JSON object. No preamble. No text outside the JSON.
"""


REPORT_TYPE = ReportType(
    id="genz_brand_tracker",
    name="Gen Z Brand Tracker",
    description="Brand social post tagging across 8 Gen Z value scores plus brand awareness, engagement, sentiment, influencer, comparison, and purchase/loyalty signals.",
    schema=GenZBrandAnalysis,
    system_prompt=GENZ_SYSTEM_PROMPT,
)
