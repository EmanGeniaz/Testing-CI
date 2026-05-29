"""Pre-baked demo runs for instant analyst demos.

Each demo carries a fully-populated session payload (raw_data, schema_config,
dataset_context, analyzed_data, report) so that loading one drops the user
into the post-tagging state immediately, with the report already generated.

The verbatims and percentages here are synthetic but written to read like
real qualitative output — quote-worthy, specific, and internally consistent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


# ── Utility ───────────────────────────────────────────────────────────────────

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
#  DEMO 1 — ALEXION HPP (Pharma Social Intelligence)
# ─────────────────────────────────────────────────────────────────────────────

_ALEXION_ANALYZED = [
    {
        "id": 1,
        "source": "Reddit r/RareDiseases",
        "date": "2025-03-14",
        "text": "My daughter spent four years going from one specialist to another before anyone even mentioned HPP. By then her bones had already started fracturing. Why is this so hard to diagnose?",
        "theme": "Diagnostic Odyssey",
        "sentiment": "Negative",
        "stage": "Pre-diagnosis",
        "unmet_need": "Timely diagnosis",
        "signal": "Diagnostic delay",
        "driver": "Specialist fragmentation",
        "confidence": "high",
        "xai_text_evidence": "four years going from one specialist to another before anyone even mentioned HPP",
        "theme_verbatim": "By then her bones had already started fracturing",
    },
    {
        "id": 2,
        "source": "Twitter / X",
        "date": "2025-03-22",
        "text": "Strensiq has been life-changing for my son. Two years on therapy and he can finally run with the other kids at school. Forever grateful to the team that finally listened.",
        "theme": "Treatment Impact",
        "sentiment": "Positive",
        "stage": "On therapy",
        "unmet_need": "Caregiver support",
        "signal": "QoL improvement",
        "driver": "Treatment efficacy",
        "confidence": "high",
        "xai_text_evidence": "he can finally run with the other kids at school",
        "qol_verbatim": "life-changing for my son",
    },
    {
        "id": 3,
        "source": "Patient forum (Inspire)",
        "date": "2025-04-02",
        "text": "Pediatrician said it was just growing pains. Orthopedist said brittle bones. Three years and four ER visits later, a geneticist finally ran the ALPL test. Adults with HPP are invisible in this system.",
        "theme": "Diagnostic Odyssey",
        "sentiment": "Negative",
        "stage": "Pre-diagnosis",
        "unmet_need": "Adult HPP recognition",
        "signal": "Misdiagnosis cascade",
        "driver": "Low disease awareness",
        "confidence": "high",
        "xai_text_evidence": "Three years and four ER visits later, a geneticist finally ran the ALPL test",
        "theme_verbatim": "Adults with HPP are invisible in this system",
    },
    {
        "id": 4,
        "source": "Reddit r/AskDocs",
        "date": "2025-04-11",
        "text": "Insurance keeps denying coverage even with confirmed ALPL mutation and low ALP. The appeal process has taken nine months and we are still fighting. Is anyone else dealing with this?",
        "theme": "Access Barriers",
        "sentiment": "Negative",
        "stage": "Treatment initiation",
        "unmet_need": "Payer access",
        "signal": "Reimbursement friction",
        "driver": "Coverage policy",
        "confidence": "high",
        "xai_text_evidence": "Insurance keeps denying coverage even with confirmed ALPL mutation",
        "theme_verbatim": "nine months and we are still fighting",
    },
    {
        "id": 5,
        "source": "Facebook patient group",
        "date": "2025-04-19",
        "text": "Has anyone switched from Strensiq to a clinical trial drug? My out-of-pocket is impossible now and I worry about losing efficacy if I switch.",
        "theme": "Treatment Decisions",
        "sentiment": "Mixed",
        "stage": "On therapy",
        "unmet_need": "Affordable therapy",
        "signal": "Switching consideration",
        "driver": "Cost burden",
        "confidence": "medium",
        "xai_text_evidence": "out-of-pocket is impossible now",
        "theme_verbatim": "worry about losing efficacy if I switch",
    },
    {
        "id": 6,
        "source": "Soft Bones community",
        "date": "2025-04-25",
        "text": "The pediatric metabolic clinic at our children's hospital was the only place that knew what HPP was. Families without access to a center of excellence have it so much harder.",
        "theme": "Care Coordination",
        "sentiment": "Mixed",
        "stage": "On therapy",
        "unmet_need": "Specialist access",
        "signal": "Center of excellence gap",
        "driver": "Geographic disparity",
        "confidence": "high",
        "xai_text_evidence": "Families without access to a center of excellence have it so much harder",
        "theme_verbatim": "the only place that knew what HPP was",
    },
    {
        "id": 7,
        "source": "Twitter / X",
        "date": "2025-05-03",
        "text": "Adult HPP is real. My ALP has been low for 20 years and every doctor dismissed it. The chronic pain and fractures are not in my head.",
        "theme": "Adult HPP Invisibility",
        "sentiment": "Negative",
        "stage": "Pre-diagnosis",
        "unmet_need": "Adult HPP recognition",
        "signal": "Provider dismissal",
        "driver": "Disease perception",
        "confidence": "high",
        "xai_text_evidence": "every doctor dismissed it",
        "theme_verbatim": "The chronic pain and fractures are not in my head",
    },
    {
        "id": 8,
        "source": "Reddit r/Parenting",
        "date": "2025-05-09",
        "text": "We saw eight specialists before our pediatric endocrinologist suggested HPP. Once we knew, treatment changed everything. I just wish the path to diagnosis was shorter.",
        "theme": "Diagnostic Odyssey",
        "sentiment": "Mixed",
        "stage": "On therapy",
        "unmet_need": "Timely diagnosis",
        "signal": "Diagnostic delay",
        "driver": "Specialist fragmentation",
        "confidence": "high",
        "xai_text_evidence": "eight specialists before our pediatric endocrinologist suggested HPP",
        "theme_verbatim": "Once we knew, treatment changed everything",
    },
]

ALEXION_DEMO = {
    "id": "demo_alexion_hpp",
    "title": "Alexion HPP — Pharma Social Intelligence",
    "description": "Patient voice intelligence on hypophosphatasia (HPP). 800 rows of patient and caregiver posts surfacing diagnostic delays, access friction, and adult-HPP invisibility.",
    "filename": "alexion_hpp_patient_voice_Q1_2025.xlsx",
    "row_count": 800,
    "report_type": "pharma_social_intelligence",
    "dataset_context": {
        "dataset_type": "Single brand (pharma — rare disease)",
        "focus_brand": "Alexion / Strensiq (HPP)",
        "additional_context": "Q1 2025 patient & caregiver voice across Reddit, X, Inspire, Soft Bones, and Facebook patient groups. Focus on hypophosphatasia (HPP) — diagnostic journey, access, and unmet needs.",
    },
    "schema_config": {
        "primary_text_column": "text",
        "visible_columns": ["source", "date", "text"],
        "ai_columns": ["theme", "sentiment", "stage", "unmet_need", "signal", "driver", "confidence"],
    },
    "analyzed_data": _ALEXION_ANALYZED,
    "report": {
        "title": "Alexion HPP — The diagnostic odyssey is the brand's defining barrier",
        "subtitle": "Patient & caregiver voice across 800 posts, Q1 2025 — Reddit, X, Inspire, Soft Bones, Facebook",
        "metadata": {
            "period": "Q1 2025",
            "items_reviewed": 800,
            "report_type": "pharma_social_intelligence",
            "generated_at": _utcnow_iso(),
            "method": "demo",
        },
        "sections": [
            {
                "id": "the-read",
                "heading": "The read",
                "body": (
                    "Across 800 patient and caregiver posts, **diagnostic delay** is the single most "
                    "frequently raised theme — **34%** of posts describe a multi-year journey before HPP "
                    "is even mentioned. Once on **Strensiq**, sentiment flips sharply positive (**+62%** "
                    "net sentiment among on-therapy posts), but **payer access** and **adult-HPP "
                    "invisibility** remain the loudest unmet needs. The community signal is clear: the "
                    "drug works; the system doesn't get patients to it fast enough."
                ),
            },
            {
                "id": "theme-distribution",
                "heading": "Theme distribution",
                "body": (
                    "**Diagnostic Odyssey**: 34%; **Treatment Impact**: 21%; **Access Barriers**: 17%; "
                    "**Adult HPP Invisibility**: 12%; **Care Coordination**: 9%; **Treatment Decisions**: 7%."
                ),
            },
            {
                "id": "sentiment-breakdown",
                "heading": "Sentiment breakdown",
                "body": (
                    "**Negative**: 48% (driven by pre-diagnosis and access posts); "
                    "**Positive**: 31% (concentrated in on-therapy patient/caregiver voice); "
                    "**Mixed**: 16%; **Neutral**: 5%. Sentiment shifts sharply by journey stage."
                ),
            },
            {
                "id": "unmet-needs",
                "heading": "Top unmet needs",
                "body": (
                    "**Timely diagnosis** (29% of posts); **Adult HPP recognition** (18%); "
                    "**Payer access** (15%); **Affordable therapy** (11%); **Specialist access / "
                    "center of excellence proximity** (9%)."
                ),
            },
            {
                "id": "disease-stages",
                "heading": "Disease stages",
                "body": (
                    "**Pre-diagnosis** posts: 41% (highest negative sentiment); **On therapy**: 38% "
                    "(highest positive sentiment); **Treatment initiation / access**: 14%; "
                    "**Off therapy / switching**: 7%."
                ),
            },
        ],
        "findings": [
            {
                "number": 1,
                "confidence": "high",
                "claim": "*Diagnostic delay is the dominant brand barrier* — patients average multi-year journeys before HPP is named.",
                "support": "34% of posts (272 of 800) describe a diagnostic odyssey; the most common specific delay cited is 3–5 years and 5+ specialists before any ALPL test is ordered.",
            },
            {
                "number": 2,
                "confidence": "high",
                "claim": "*Adult HPP is functionally invisible in the system* — adults report repeated provider dismissal of low ALP.",
                "support": "12% of all posts (96) are adult-HPP-specific; 78% of those mention being dismissed or misdiagnosed before reaching a geneticist or metabolic specialist.",
            },
            {
                "number": 3,
                "confidence": "high",
                "claim": "*Strensiq delivers a clear QoL story* — once patients reach therapy, caregiver voice is overwhelmingly positive.",
                "support": "On-therapy posts run +62% net positive sentiment. Specific QoL mentions cluster around mobility, school participation, and fracture reduction.",
            },
            {
                "number": 4,
                "confidence": "medium",
                "claim": "*Payer friction is creating a secondary attrition risk* even for confirmed HPP patients.",
                "support": "17% of posts describe coverage denials, appeals taking 6–12 months, and out-of-pocket cost pushing patients to consider switching off therapy.",
            },
            {
                "number": 5,
                "confidence": "medium",
                "claim": "*Center-of-excellence proximity predicts patient experience* — geographic gaps drive material disparities.",
                "support": "9% of posts cite the absence of a nearby metabolic / genetics clinic as the root cause of their delay; positive sentiment is 2.4x higher among posts mentioning a named center of excellence.",
            },
        ],
        "evidence": [
            {
                "source": "Reddit r/RareDiseases",
                "quote": "My daughter spent four years going from one specialist to another before anyone even mentioned HPP. By then her bones had already started fracturing.",
                "tags": ["Diagnostic Odyssey", "Pre-diagnosis", "Timely diagnosis"],
                "sentiment": "negative",
            },
            {
                "source": "Twitter / X",
                "quote": "Strensiq has been life-changing for my son. Two years on therapy and he can finally run with the other kids at school.",
                "tags": ["Treatment Impact", "On therapy", "QoL improvement"],
                "sentiment": "positive",
            },
            {
                "source": "Patient forum (Inspire)",
                "quote": "Adults with HPP are invisible in this system.",
                "tags": ["Adult HPP Invisibility", "Pre-diagnosis"],
                "sentiment": "negative",
            },
            {
                "source": "Reddit r/AskDocs",
                "quote": "Insurance keeps denying coverage even with confirmed ALPL mutation and low ALP. The appeal process has taken nine months and we are still fighting.",
                "tags": ["Access Barriers", "Payer access"],
                "sentiment": "negative",
            },
            {
                "source": "Soft Bones community",
                "quote": "The pediatric metabolic clinic at our children's hospital was the only place that knew what HPP was.",
                "tags": ["Care Coordination", "Center of excellence gap"],
                "sentiment": "mixed",
            },
            {
                "source": "Twitter / X",
                "quote": "My ALP has been low for 20 years and every doctor dismissed it. The chronic pain and fractures are not in my head.",
                "tags": ["Adult HPP Invisibility", "Provider dismissal"],
                "sentiment": "negative",
            },
        ],
        "so_what": (
            "Lead with a diagnostic-acceleration narrative: HCP education on ALP testing, "
            "amplification of patient stories from named centers of excellence, and a focused "
            "play on adult-HPP recognition. Pair that with concrete payer-access investment "
            "(case management, appeals support) — the drug's QoL story is strong enough to "
            "carry the brand once patients can actually reach it."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  DEMO 2 — LIQUID DEATH (Brand Insights)
# ─────────────────────────────────────────────────────────────────────────────

_LIQUID_DEATH_ANALYZED = [
    {
        "id": 1,
        "source": "TikTok",
        "date": "2025-02-08",
        "text": "Liquid Death at Whole Foods just hits different. The cans look like they belong in a record shop, not a beverage aisle. I am buying water for the aesthetic at this point.",
        "theme": "Aesthetic Pull",
        "sentiment": "Positive",
        "signal": "Cultural cachet",
        "driver": "Visual identity",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "I am buying water for the aesthetic at this point",
        "theme_verbatim": "look like they belong in a record shop",
    },
    {
        "id": 2,
        "source": "Reddit r/marketing",
        "date": "2025-02-14",
        "text": "Liquid Death's whole shtick worked when they were a scrappy upstart. Now they sponsor the NFL and sell at Target. The punk thing starts to ring hollow when you're a billion-dollar brand.",
        "theme": "Authenticity Erosion",
        "sentiment": "Negative",
        "signal": "Sell-out perception",
        "driver": "Scale vs. brand promise",
        "audience": "Millennial",
        "confidence": "high",
        "xai_text_evidence": "The punk thing starts to ring hollow when you're a billion-dollar brand",
        "theme_verbatim": "they sponsor the NFL and sell at Target",
    },
    {
        "id": 3,
        "source": "Twitter / X",
        "date": "2025-02-21",
        "text": "Hot take: Liquid Death is the first beverage brand I have actually wanted to wear as merch. The skater collab was insane.",
        "theme": "Brand-as-Identity",
        "sentiment": "Positive",
        "signal": "Merch demand",
        "driver": "Collab strategy",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "first beverage brand I have actually wanted to wear as merch",
    },
    {
        "id": 4,
        "source": "Instagram",
        "date": "2025-03-04",
        "text": "Bought a 12-pack of Liquid Death because the can said Murder Your Thirst. It's just water. But honestly? Best water I've had this year and I'm not even being ironic.",
        "theme": "Product Surprise",
        "sentiment": "Positive",
        "signal": "Trial-to-loyalty conversion",
        "driver": "Packaging copy",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "Best water I've had this year and I'm not even being ironic",
    },
    {
        "id": 5,
        "source": "Reddit r/hydrohomies",
        "date": "2025-03-10",
        "text": "I love Liquid Death but their cans cost $2 for what is literally tap water. The premium pricing only works while the brand is cool.",
        "theme": "Price Sensitivity",
        "sentiment": "Mixed",
        "signal": "Pricing fragility",
        "driver": "Cultural relevance dependency",
        "audience": "Millennial",
        "confidence": "medium",
        "xai_text_evidence": "The premium pricing only works while the brand is cool",
    },
    {
        "id": 6,
        "source": "TikTok",
        "date": "2025-03-19",
        "text": "Live Fast Die Old. Death To Plastic. The slogans alone have made me drink more water than any wellness influencer ever has.",
        "theme": "Sustainability Halo",
        "sentiment": "Positive",
        "signal": "Anti-plastic messaging",
        "driver": "Cause alignment",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "made me drink more water than any wellness influencer ever has",
    },
    {
        "id": 7,
        "source": "YouTube comments",
        "date": "2025-03-28",
        "text": "The Martha Stewart ad was peak Liquid Death. Nobody else would have made that. That's the brand — totally unpredictable.",
        "theme": "Marketing Earned Media",
        "sentiment": "Positive",
        "signal": "Viral campaign equity",
        "driver": "Creative risk-taking",
        "audience": "Gen Z + Millennial",
        "confidence": "high",
        "xai_text_evidence": "Nobody else would have made that",
    },
    {
        "id": 8,
        "source": "Reddit r/beverages",
        "date": "2025-04-02",
        "text": "Switched to Liquid Death iced tea sparkling. The flavored line is actually better than the still water IMO. They're quietly becoming a real beverage company.",
        "theme": "Portfolio Expansion",
        "sentiment": "Positive",
        "signal": "Line extension acceptance",
        "driver": "Product quality",
        "audience": "Millennial",
        "confidence": "high",
        "xai_text_evidence": "The flavored line is actually better than the still water",
    },
]

LIQUID_DEATH_DEMO = {
    "id": "demo_liquid_death",
    "title": "Liquid Death — Brand Insights",
    "description": "600 posts of brand-health intelligence on Liquid Death. The signature tension: punk-authenticity equity vs. mainstream growth.",
    "filename": "liquid_death_brand_health_Q1_2025.xlsx",
    "row_count": 600,
    "report_type": "brand_health",
    "dataset_context": {
        "dataset_type": "Single brand (CPG — beverages)",
        "focus_brand": "Liquid Death",
        "additional_context": "Q1 2025 brand health pulse across TikTok, X, Reddit, Instagram, and YouTube. Focus on brand equity drivers, cultural relevance, and the punk-vs-scale tension as the brand matures.",
    },
    "schema_config": {
        "primary_text_column": "text",
        "visible_columns": ["source", "date", "text"],
        "ai_columns": ["theme", "sentiment", "signal", "driver", "audience", "confidence"],
    },
    "analyzed_data": _LIQUID_DEATH_ANALYZED,
    "report": {
        "title": "Liquid Death — The punk equity is winning, but the cracks are showing",
        "subtitle": "Brand health pulse across 600 posts, Q1 2025 — TikTok, X, Reddit, Instagram, YouTube",
        "metadata": {
            "period": "Q1 2025",
            "items_reviewed": 600,
            "report_type": "brand_health",
            "generated_at": _utcnow_iso(),
            "method": "demo",
        },
        "sections": [
            {
                "id": "the-read",
                "heading": "The read",
                "body": (
                    "Liquid Death is still riding **+47% net positive sentiment** — extraordinary for "
                    "a CPG brand at this scale. **Aesthetic pull** and **brand-as-identity** are the "
                    "two dominant equity drivers (combined **39%** of posts). But **authenticity "
                    "erosion** has emerged as a real countersignal: **18%** of posts now question "
                    "whether the punk positioning survives mainstream distribution, NFL sponsorship, "
                    "and a multi-billion-dollar valuation. The brand is at a classic inflection — "
                    "the cultural cachet that built it is the same thing that's most at risk."
                ),
            },
            {
                "id": "theme-distribution",
                "heading": "Theme distribution",
                "body": (
                    "**Aesthetic Pull**: 22%; **Brand-as-Identity**: 17%; **Authenticity Erosion**: 18%; "
                    "**Sustainability Halo**: 13%; **Product Surprise**: 11%; **Marketing Earned Media**: "
                    "9%; **Portfolio Expansion**: 6%; **Price Sensitivity**: 4%."
                ),
            },
            {
                "id": "sentiment-breakdown",
                "heading": "Sentiment breakdown",
                "body": (
                    "**Positive**: 58%; **Negative**: 11%; **Mixed**: 24%; **Neutral**: 7%. "
                    "Net positive sentiment **+47%** — top-decile vs. CPG brand benchmark. "
                    "Negative concentration is in Millennial cohort, not Gen Z."
                ),
            },
            {
                "id": "signal-distribution",
                "heading": "Signals detected",
                "body": (
                    "**Cultural cachet**: 142 mentions; **Sell-out perception**: 108; **Viral campaign "
                    "equity**: 86; **Merch demand**: 71; **Anti-plastic messaging**: 64; "
                    "**Trial-to-loyalty conversion**: 52."
                ),
            },
            {
                "id": "driver-distribution",
                "heading": "Top narrative drivers",
                "body": (
                    "**Visual identity** (cans, packaging copy); **Creative risk-taking** (Martha Stewart "
                    "ad, brand collabs); **Scale vs. brand promise** (NFL deal, mass distribution); "
                    "**Cause alignment** (anti-plastic, Death To Plastic platform)."
                ),
            },
        ],
        "findings": [
            {
                "number": 1,
                "confidence": "high",
                "claim": "*The aesthetic is the product* — 22% of posts treat Liquid Death as a visual/cultural object first and a beverage second.",
                "support": "132 of 600 posts explicitly cite can design, packaging copy, or merch as the purchase driver. Phrases like 'buying for the aesthetic' recur 47 times.",
            },
            {
                "number": 2,
                "confidence": "high",
                "claim": "*Authenticity erosion is the single biggest emerging risk* — 18% of posts question the punk positioning at current scale.",
                "support": "108 posts cite NFL deal, mass retail distribution, or valuation milestones as evidence the brand has 'sold out'. Concentration is Millennial cohort (66% of negative posts).",
            },
            {
                "number": 3,
                "confidence": "high",
                "claim": "*Earned media equity is structural, not lucky* — campaigns like the Martha Stewart spot are reinforcing 'creative risk-taking' as a permanent brand attribute.",
                "support": "86 posts reference specific campaigns as proof of brand identity. The brand is being treated as a creative entity ('peak Liquid Death'), not just a beverage marketer.",
            },
            {
                "number": 4,
                "confidence": "medium",
                "claim": "*The sparkling-tea / portfolio extension is landing* — line extensions are being received as quality plays, not desperation moves.",
                "support": "36 posts specifically about flavored/iced-tea line, with 81% positive sentiment. Phrases like 'quietly becoming a real beverage company' suggest growth without brand dilution — for now.",
            },
            {
                "number": 5,
                "confidence": "medium",
                "claim": "*Price tolerance is brand-conditional* — premium pricing is supported by cultural relevance, and fragile to it.",
                "support": "24 posts explicitly flag $2/can as 'fine while the brand is cool' — pricing power is tied to the same equity that authenticity erosion threatens. Risk compounds.",
            },
        ],
        "evidence": [
            {
                "source": "TikTok",
                "quote": "Liquid Death at Whole Foods just hits different. The cans look like they belong in a record shop, not a beverage aisle. I am buying water for the aesthetic at this point.",
                "tags": ["Aesthetic Pull", "Cultural cachet"],
                "sentiment": "positive",
            },
            {
                "source": "Reddit r/marketing",
                "quote": "The punk thing starts to ring hollow when you're a billion-dollar brand.",
                "tags": ["Authenticity Erosion", "Sell-out perception"],
                "sentiment": "negative",
            },
            {
                "source": "Twitter / X",
                "quote": "Liquid Death is the first beverage brand I have actually wanted to wear as merch.",
                "tags": ["Brand-as-Identity", "Merch demand"],
                "sentiment": "positive",
            },
            {
                "source": "YouTube comments",
                "quote": "The Martha Stewart ad was peak Liquid Death. Nobody else would have made that. That's the brand — totally unpredictable.",
                "tags": ["Marketing Earned Media", "Creative risk-taking"],
                "sentiment": "positive",
            },
            {
                "source": "Reddit r/hydrohomies",
                "quote": "The premium pricing only works while the brand is cool.",
                "tags": ["Price Sensitivity", "Cultural relevance dependency"],
                "sentiment": "mixed",
            },
            {
                "source": "Reddit r/beverages",
                "quote": "The flavored line is actually better than the still water IMO. They're quietly becoming a real beverage company.",
                "tags": ["Portfolio Expansion", "Line extension acceptance"],
                "sentiment": "positive",
            },
        ],
        "so_what": (
            "Double down on the creative-risk muscle that earned-media is rewarding, and keep "
            "the visual/aesthetic equity protected at all costs — that is the brand. But the "
            "Millennial authenticity-erosion signal is real and shouldn't be dismissed; consider "
            "deliberate counter-signals (independent collabs, cause activations, refusal of obvious "
            "scale plays) that reinforce the punk DNA even as distribution grows. Pricing power and "
            "portfolio extension success both depend on the brand staying culturally hot."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  DEMO 3 — NIKE vs ADIDAS (Gen Z Brand Tracker)
# ─────────────────────────────────────────────────────────────────────────────

_NIKE_ADIDAS_ANALYZED = [
    {
        "id": 1,
        "source": "TikTok",
        "date": "2025-01-22",
        "text": "Adidas Sambas have officially replaced Air Force 1s in my rotation. Nike feels like what my dad wears to the gym now.",
        "theme": "Cultural Shift",
        "sentiment": "Positive (Adidas)",
        "brand": "Adidas",
        "signal": "Style migration",
        "driver": "Silhouette relevance",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "Nike feels like what my dad wears to the gym now",
    },
    {
        "id": 2,
        "source": "Reddit r/Sneakers",
        "date": "2025-01-30",
        "text": "Nike's sustainability messaging feels performative. Adidas at least has the Parley line and the Stan Smith recycled materials. Both could do more.",
        "theme": "Sustainability Credibility",
        "sentiment": "Negative (Nike) / Mixed (Adidas)",
        "brand": "Both",
        "signal": "Greenwashing perception",
        "driver": "Product-level proof",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "Nike's sustainability messaging feels performative",
        "theme_verbatim": "Adidas at least has the Parley line",
    },
    {
        "id": 3,
        "source": "Twitter / X",
        "date": "2025-02-05",
        "text": "Adidas's Yeezy fallout cost them my trust, not gonna lie. Nike's WNBA partnership has been actually meaningful. Culture work matters.",
        "theme": "Cultural Alignment",
        "sentiment": "Negative (Adidas) / Positive (Nike)",
        "brand": "Both",
        "signal": "Partnership equity",
        "driver": "Athlete & cultural moments",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "Adidas's Yeezy fallout cost them my trust",
    },
    {
        "id": 4,
        "source": "Instagram",
        "date": "2025-02-13",
        "text": "Got the Adidas Gazelles in mocha and I genuinely cannot stop wearing them. The 90s revival is hitting and Adidas is winning it.",
        "theme": "Trend Capture",
        "sentiment": "Positive (Adidas)",
        "brand": "Adidas",
        "signal": "Retro silhouette momentum",
        "driver": "Y2K / 90s aesthetic",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "The 90s revival is hitting and Adidas is winning it",
    },
    {
        "id": 5,
        "source": "TikTok",
        "date": "2025-02-21",
        "text": "Nike's running shoes are still S tier. Vaporfly literally changed marathon culture. For performance I still pick Nike, but for fits I'm wearing Sambas.",
        "theme": "Performance vs. Style",
        "sentiment": "Mixed",
        "brand": "Both",
        "signal": "Use-case bifurcation",
        "driver": "Product specialization",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "for performance I still pick Nike, but for fits I'm wearing Sambas",
    },
    {
        "id": 6,
        "source": "Reddit r/femalefashionadvice",
        "date": "2025-03-02",
        "text": "Nike has not made a single sneaker I have wanted in two years. Adidas, New Balance, even Asics are eating their lunch with the under-25 crowd.",
        "theme": "Innovation Gap",
        "sentiment": "Negative (Nike)",
        "brand": "Nike",
        "signal": "Product fatigue",
        "driver": "Design pipeline",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "Adidas, New Balance, even Asics are eating their lunch with the under-25 crowd",
    },
    {
        "id": 7,
        "source": "YouTube",
        "date": "2025-03-11",
        "text": "Nike's response to the F1 partnership has been weak. Adidas going hard on football and Olympics — that's the playbook now. Culture moves through sport.",
        "theme": "Sport-Culture Strategy",
        "sentiment": "Positive (Adidas) / Mixed (Nike)",
        "brand": "Both",
        "signal": "Sport sponsorship strategy",
        "driver": "Cultural moment capture",
        "audience": "Gen Z + Millennial",
        "confidence": "medium",
        "xai_text_evidence": "Culture moves through sport",
    },
    {
        "id": 8,
        "source": "Twitter / X",
        "date": "2025-03-18",
        "text": "Adidas Originals doing more for sustainability through Parley than Nike's entire Move to Zero campaign. Show, don't tell.",
        "theme": "Sustainability Credibility",
        "sentiment": "Positive (Adidas) / Negative (Nike)",
        "brand": "Both",
        "signal": "Proof-point preference",
        "driver": "Product-led sustainability",
        "audience": "Gen Z",
        "confidence": "high",
        "xai_text_evidence": "Show, don't tell",
    },
]

NIKE_ADIDAS_DEMO = {
    "id": "demo_nike_adidas",
    "title": "Nike vs Adidas — Gen Z Brand Tracker",
    "description": "500 posts of Gen Z brand perception across Nike and Adidas. The two cuts that matter: sustainability credibility and cultural alignment.",
    "filename": "nike_vs_adidas_genz_tracker_Q1_2025.xlsx",
    "row_count": 500,
    "report_type": "competitive_intelligence",
    "dataset_context": {
        "dataset_type": "Competitive (two-brand comparison)",
        "focus_brand": "Nike vs Adidas",
        "additional_context": "Q1 2025 Gen Z brand tracker across TikTok, X, Reddit, Instagram, and YouTube. Focus on youth perception, with primary cuts on sustainability credibility and cultural / subcultural alignment.",
    },
    "schema_config": {
        "primary_text_column": "text",
        "visible_columns": ["source", "date", "text"],
        "ai_columns": ["theme", "sentiment", "brand", "signal", "driver", "audience", "confidence"],
    },
    "analyzed_data": _NIKE_ADIDAS_ANALYZED,
    "report": {
        "title": "Nike vs Adidas — Adidas is winning Gen Z's wardrobe; Nike still owns the run",
        "subtitle": "Gen Z brand tracker across 500 posts, Q1 2025 — TikTok, X, Reddit, Instagram, YouTube",
        "metadata": {
            "period": "Q1 2025",
            "items_reviewed": 500,
            "report_type": "competitive_intelligence",
            "generated_at": _utcnow_iso(),
            "method": "demo",
        },
        "sections": [
            {
                "id": "the-read",
                "heading": "The read",
                "body": (
                    "Gen Z is splitting Nike and Adidas by use-case in a way that materially favors "
                    "Adidas on culture and Nike on performance. Adidas leads **net positive sentiment "
                    "by +21 points** (+44 vs +23). Two themes carry the gap: **cultural alignment** "
                    "(Sambas, Gazelles, Y2K/90s revival) and **sustainability credibility** (Parley / "
                    "product-level proof vs. perceived performative Nike messaging). Nike's strongest "
                    "remaining moat is **performance running and women's sport partnerships** — both "
                    "real, both narrower than the brand needs."
                ),
            },
            {
                "id": "theme-distribution",
                "heading": "Theme distribution",
                "body": (
                    "**Cultural Shift / Style migration**: 24%; **Sustainability Credibility**: 19%; "
                    "**Cultural Alignment**: 15%; **Trend Capture (Y2K/90s)**: 13%; "
                    "**Performance vs. Style**: 11%; **Innovation Gap**: 9%; "
                    "**Sport-Culture Strategy**: 7%; **Other**: 2%."
                ),
            },
            {
                "id": "sentiment-breakdown",
                "heading": "Sentiment breakdown — by brand",
                "body": (
                    "**Adidas**: 58% positive / 14% negative / 24% mixed / 4% neutral (net **+44**). "
                    "**Nike**: 41% positive / 18% negative / 33% mixed / 8% neutral (net **+23**). "
                    "Adidas leads by **+21 net sentiment points** with the Gen Z cohort."
                ),
            },
            {
                "id": "signal-distribution",
                "heading": "Signals detected",
                "body": (
                    "**Style migration**: 102 mentions; **Greenwashing perception**: 71; "
                    "**Retro silhouette momentum**: 65; **Partnership equity**: 54; "
                    "**Product fatigue (Nike)**: 49; **Use-case bifurcation**: 38."
                ),
            },
            {
                "id": "driver-distribution",
                "heading": "Top narrative drivers",
                "body": (
                    "**Silhouette relevance** (Sambas, Gazelles); **Y2K / 90s aesthetic** (retro "
                    "revival); **Product-level sustainability proof** (Parley line); **Athlete & "
                    "cultural moments** (WNBA for Nike, football/Olympics for Adidas); "
                    "**Design pipeline freshness**."
                ),
            },
        ],
        "findings": [
            {
                "number": 1,
                "confidence": "high",
                "claim": "*Adidas has captured the Gen Z everyday wardrobe* — Sambas and Gazelles are the dominant 'cultural shift' signal.",
                "support": "24% of all posts (120 of 500) cite style migration from Nike to Adidas silhouettes. 'Sambas replacing Air Force 1s' appears as a near-verbatim refrain across 31 posts.",
            },
            {
                "number": 2,
                "confidence": "high",
                "claim": "*Sustainability credibility is decided at the product level, not the campaign level* — and Gen Z is reading Adidas as more credible.",
                "support": "19% of posts engage with sustainability; among those, 67% favor Adidas's Parley line over Nike's Move to Zero. Recurring critique: Nike messages, Adidas ships — 'show, don't tell'.",
            },
            {
                "number": 3,
                "confidence": "high",
                "claim": "*Nike retains performance-running supremacy* — the use-case bifurcation is real and stable.",
                "support": "11% of posts explicitly separate performance (Nike-favored: Vaporfly, Pegasus) from style (Adidas-favored). 'Performance Nike, style Adidas' pattern recurs in 28 posts.",
            },
            {
                "number": 4,
                "confidence": "medium",
                "claim": "*Adidas's Yeezy fallout has not fully cleared* — partnership-equity risk is still being priced into the brand.",
                "support": "8% of posts still reference the Yeezy / Ye situation as a trust factor, primarily older Gen Z (21–26). Nike's WNBA and women's sport activations are picking up some of the trust loss.",
            },
            {
                "number": 5,
                "confidence": "medium",
                "claim": "*Nike has an innovation-pipeline perception problem with under-25s* that goes beyond style — it's being read as a design fatigue signal.",
                "support": "9% of posts (45) frame Nike as out of step with the cohort; 'haven't wanted a Nike in two years' style phrasing appears in 19 posts. Direct competitive callouts now include New Balance and Asics, not just Adidas.",
            },
        ],
        "evidence": [
            {
                "source": "TikTok",
                "quote": "Adidas Sambas have officially replaced Air Force 1s in my rotation. Nike feels like what my dad wears to the gym now.",
                "tags": ["Cultural Shift", "Style migration", "Adidas"],
                "sentiment": "positive",
            },
            {
                "source": "Twitter / X",
                "quote": "Adidas Originals doing more for sustainability through Parley than Nike's entire Move to Zero campaign. Show, don't tell.",
                "tags": ["Sustainability Credibility", "Product-led sustainability"],
                "sentiment": "mixed",
            },
            {
                "source": "Reddit r/Sneakers",
                "quote": "Nike's sustainability messaging feels performative.",
                "tags": ["Sustainability Credibility", "Greenwashing perception", "Nike"],
                "sentiment": "negative",
            },
            {
                "source": "TikTok",
                "quote": "For performance I still pick Nike, but for fits I'm wearing Sambas.",
                "tags": ["Performance vs. Style", "Use-case bifurcation"],
                "sentiment": "mixed",
            },
            {
                "source": "Reddit r/femalefashionadvice",
                "quote": "Adidas, New Balance, even Asics are eating their lunch with the under-25 crowd.",
                "tags": ["Innovation Gap", "Product fatigue", "Nike"],
                "sentiment": "negative",
            },
            {
                "source": "Instagram",
                "quote": "The 90s revival is hitting and Adidas is winning it.",
                "tags": ["Trend Capture", "Y2K / 90s aesthetic"],
                "sentiment": "positive",
            },
        ],
        "so_what": (
            "For Nike: protect the performance moat (running, women's sport) and treat the "
            "innovation-pipeline perception as a strategic priority, not a marketing one — Gen "
            "Z is naming specific competitors by name. Sustainability needs product-level proof, "
            "not campaign-level messaging. For Adidas: the Sambas/Gazelles cultural moment is real "
            "but cyclical — invest now in the next silhouette that earns the same equity, and keep "
            "Parley front-and-center as the credibility anchor. Yeezy trust drag is fading but not "
            "gone; partnerships chosen now will reset the next 24 months of cultural credit."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

DEMO_RUNS: dict[str, dict] = {
    ALEXION_DEMO["id"]: ALEXION_DEMO,
    LIQUID_DEATH_DEMO["id"]: LIQUID_DEATH_DEMO,
    NIKE_ADIDAS_DEMO["id"]: NIKE_ADIDAS_DEMO,
}


def list_demos() -> list[dict]:
    """Lightweight metadata for the /demos endpoint."""
    return [
        {
            "id": demo["id"],
            "title": demo["title"],
            "description": demo["description"],
            "filename": demo["filename"],
            "row_count": demo["row_count"],
            "report_type": demo["report_type"],
            "focus_brand": demo["dataset_context"].get("focus_brand", ""),
            "findings_count": len(demo["report"].get("findings", [])),
        }
        for demo in DEMO_RUNS.values()
    ]


def get_demo(demo_id: str) -> Optional[dict]:
    return DEMO_RUNS.get(demo_id)


def build_demo_session(demo_id: str, session_id: str) -> Optional[dict]:
    """Materialize a demo into a session-shaped dict ready to drop into the DB.

    `session_id` is the new ID assigned to this user's instance of the demo;
    the demo template stays untouched so multiple users can load the same demo
    without colliding.
    """
    demo = get_demo(demo_id)
    if not demo:
        return None

    now = _utcnow_iso()
    analyzed = [dict(row) for row in demo["analyzed_data"]]

    # Derive a tiny "preview" + "raw_data" view so the rest of the app's
    # session-shape assumptions hold (preview is used by the UI; raw_data
    # is what /upload would have produced).
    preview = analyzed[:4]
    columns = list({k for row in analyzed for k in row.keys()})

    session_payload = {
        "session_id": session_id,
        "filename": demo["filename"],
        "columns": columns,
        "raw_data": analyzed,
        "preview": preview,
        "dataset_context": dict(demo["dataset_context"]),
        "schema_config": dict(demo["schema_config"]),
        "analyzed_data": analyzed,
        "report": dict(demo["report"]),
        "report_type": demo["report_type"],
        "status": "complete",
        "progress": 100,
        "created_at": now,
        "updated_at": now,
        "is_demo": True,
        "demo_id": demo_id,
        "demo_title": demo["title"],
        "row_count": demo["row_count"],
    }
    return session_payload
