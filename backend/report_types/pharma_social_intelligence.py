"""Pharma Social Intelligence — Monisha's methodology.

Models social posts about a disease area as a set of findings across five
dimensions: Stage, Theme, Unmet Need, Concern, QoL Impact. Each finding
carries its own verbatim evidence quote. A single input post can produce
zero, one, or many findings depending on how much insight it contains —
mirroring the structure of Monisha's hand-coded Alexion HPP sheet, where
most rows are blank for the tag columns and only insight-bearing posts
get coded (sometimes with multiple rows per post for multi-finding posts).

Controlled vocabularies are extracted from the Alexion coding workbook.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from .base import ReportType


# ── Controlled vocabularies ──────────────────────────────────────────────────
# Kept as plain strings (not Literal) so the LLM can extend with adjacent terms
# when the post genuinely doesn't fit. The prompt strongly steers to these.

STAGE_VOCAB = ["PreDiagnosis", "Symptomatic", "Diagnosis", "Treatment", "Management"]
QOL_IMPACT_VOCAB = ["Emotional", "Physical", "Occupational", "Financial", "Social"]
REPORTER_TYPE_VOCAB = ["Patient", "Caregiver", "HCP", "Advocacy", "Researcher", "Unknown"]


class PharmaSIFinding(BaseModel):
    """One distinct insight extracted from a post. A post can yield multiple
    findings — for example a Theme finding plus an Unmet Need finding plus a
    QoL finding, each with its own verbatim. Fields that don't apply for this
    particular finding should be left as empty strings."""

    stage: str = Field(
        default="",
        description=(
            "Disease/treatment stage the post discusses. One of: "
            + ", ".join(STAGE_VOCAB)
            + ". Empty string if not clearly indicated."
        ),
    )
    theme: str = Field(
        default="",
        description=(
            "Primary clinical or experiential theme (e.g. 'Symptom Burdens', "
            "'Diagnostic Challenges', 'Treatment Side Effects'). Use 2-4 word "
            "noun phrases. Empty string if no clear theme."
        ),
    )
    theme_verbatim: str = Field(
        default="",
        description="EXACT verbatim quote from the post supporting the theme. Direct copy-paste, no paraphrase. Empty if theme is empty.",
    )
    unmet_need: str = Field(
        default="",
        description=(
            "Specific unmet patient/caregiver need surfaced in the post "
            "(e.g. 'Timely and Accurate Diagnosis', 'Insurance Policy Coverage', "
            "'Reliable Resource Materials'). Empty string if none."
        ),
    )
    unmet_need_verbatim: str = Field(
        default="",
        description="EXACT verbatim quote supporting the unmet need. Empty if unmet_need is empty.",
    )
    concern: str = Field(
        default="",
        description=(
            "Specific concern raised (e.g. 'Diagnostic Challenges', "
            "'Expensive Treatment', 'Lack of Awareness', 'Mobility Issues'). "
            "Empty string if none."
        ),
    )
    concern_verbatim: str = Field(
        default="",
        description="EXACT verbatim quote supporting the concern. Empty if concern is empty.",
    )
    qol_impact: str = Field(
        default="",
        description=(
            "Quality-of-life domain impacted. One of: "
            + ", ".join(QOL_IMPACT_VOCAB)
            + ". Empty string if no QoL impact is discussed."
        ),
    )
    qol_sub_issue: str = Field(
        default="",
        description=(
            "More specific QoL sub-issue (e.g. 'Anxiety', 'Career Aspirations "
            "Affected', 'Adverse Effects from Medication', 'Isolation', "
            "'Frustration'). Empty if qol_impact is empty."
        ),
    )
    qol_verbatim: str = Field(
        default="",
        description="EXACT verbatim quote supporting the QoL impact. Empty if qol_impact is empty.",
    )

    def is_empty(self) -> bool:
        return not any([
            self.stage, self.theme, self.unmet_need,
            self.concern, self.qol_impact,
        ])


class PharmaSIAnalysis(BaseModel):
    """Wrapping schema: the LLM emits one of these per input post.

    Most posts yield zero findings (chit-chat, off-topic, generic awareness
    content). Insight-rich posts yield 1-3 findings.
    """

    reporter_type: str = Field(
        default="Unknown",
        description=(
            "Who is speaking in this post. One of: "
            + ", ".join(REPORTER_TYPE_VOCAB)
            + ". Default 'Unknown' if not inferable."
        ),
    )
    findings: List[PharmaSIFinding] = Field(
        default_factory=list,
        description=(
            "Zero or more distinct findings extracted from this post. Most "
            "posts produce zero findings (do NOT force a finding for chit-chat, "
            "generic awareness content, or posts with no actionable insight). "
            "Insight-bearing posts typically produce 1-3 findings."
        ),
    )
    rationale: str = Field(
        default="",
        description="One-line rationale explaining why these findings were extracted (or why none were).",
    )


PHARMA_SI_SYSTEM_PROMPT = """You are a Pharma Social Intelligence analyst extracting structured insights from social media posts about a specific disease area for a pharmaceutical strategy team.

Your job is NOT to summarize every post. Your job is to surface the small subset of posts that contain real patient/caregiver/HCP insights that would inform pharma strategy, and tag them precisely.

=== DISEASE AREA CONTEXT ===
Disease / Therapy Area: {brand_focus}
Dataset notes: {dataset_type}
Additional context: {additional_context}

=== METHODOLOGY ===

For the source post below, decide whether it contains any actionable insight along ANY of these five dimensions:

1. STAGE OF DISEASE — Which point in the disease/treatment journey is the author discussing?
   Controlled vocabulary: PreDiagnosis, Symptomatic, Diagnosis, Treatment, Management

2. THEME — What clinical or experiential theme is the post primarily about?
   Examples: "Symptom Burdens", "Diagnostic Challenges", "Treatment Side Effects",
   "Insurance Barriers", "Caregiver Burden". 2-4 word noun phrases.

3. UNMET NEED — What specific need is being expressed or implied that current
   healthcare/pharma is not meeting? Examples: "Timely and Accurate Diagnosis",
   "Insurance Policy Coverage", "Reliable Resource Materials",
   "Individualized Treatment Plans", "Research for Rare Diseases".

4. CONCERN — What specific concern is being raised? Examples:
   "Diagnostic Challenges", "Expensive Treatment", "Lack of Awareness",
   "Mobility Issues", "Potential for Misdiagnosis".

5. QoL IMPACT — Which quality-of-life domain is affected?
   Controlled vocabulary: Emotional, Physical, Occupational, Financial, Social
   Plus a more specific sub-issue (e.g. "Anxiety", "Career Aspirations Affected",
   "Adverse Effects from Medication", "Isolation;Frustration").

=== FINDINGS RULES ===

- Produce a SEPARATE finding object for each distinct insight, not one omnibus finding.
  Example: a post that describes a diagnostic delay AND mentions insurance denials
  AND describes emotional toll → 3 separate findings (Theme=Diagnostic Challenges,
  Unmet Need=Insurance Coverage, QoL Impact=Emotional).
- A finding may use any subset of the 5 dimensions — fields that don't apply are
  left as empty strings. E.g. a finding may carry only Theme + theme_verbatim.
- EVERY non-empty tag must have a corresponding verbatim quote that is an EXACT
  copy-paste from the source post. No paraphrasing, no fabrication. If you cannot
  find a verbatim, leave the tag empty.
- If the post contains NO actionable insight (chit-chat, generic awareness,
  off-topic), return findings=[]. This is normal and expected for most posts.

=== REPORTER TYPE ===
Who is speaking? One of: Patient, Caregiver, HCP, Advocacy, Researcher, Unknown.

=== RARE DISEASE GUIDANCE ===
If the disease area is rare, be especially attentive to: diagnostic delays,
heavy reliance on advocacy/community, access and reimbursement complexity,
small fragmented populations.

=== SOURCE POST ===
{source_text}

=== OUTPUT FORMAT ===
{format_instructions}

Produce ONLY the JSON object. No preamble. No text outside the JSON.
Most posts should return findings=[]. Do NOT force a finding to look productive.
"""


def _pharma_si_post_processor(raw_row: dict, parsed: dict) -> list[dict]:
    """Expand the wrapping analysis into one output row per finding.

    - 0 findings → 1 row with empty tag fields and a _has_finding=False flag
    - N findings → N rows, each with the raw input + one finding's fields
    - reporter_type and rationale are carried onto every emitted row
    """
    reporter_type = parsed.get("reporter_type", "Unknown")
    rationale     = parsed.get("rationale", "")
    findings      = parsed.get("findings") or []

    if not findings:
        empty_finding = {
            "stage": "", "theme": "", "theme_verbatim": "",
            "unmet_need": "", "unmet_need_verbatim": "",
            "concern": "", "concern_verbatim": "",
            "qol_impact": "", "qol_sub_issue": "", "qol_verbatim": "",
        }
        return [{
            **raw_row,
            "reporter_type": reporter_type,
            **empty_finding,
            "_has_finding": False,
            "_finding_index": 0,
            "_finding_count": 0,
            "rationale": rationale,
        }]

    out = []
    for i, f in enumerate(findings):
        out.append({
            **raw_row,
            "reporter_type": reporter_type,
            "stage":               f.get("stage", ""),
            "theme":               f.get("theme", ""),
            "theme_verbatim":      f.get("theme_verbatim", ""),
            "unmet_need":          f.get("unmet_need", ""),
            "unmet_need_verbatim": f.get("unmet_need_verbatim", ""),
            "concern":             f.get("concern", ""),
            "concern_verbatim":    f.get("concern_verbatim", ""),
            "qol_impact":          f.get("qol_impact", ""),
            "qol_sub_issue":       f.get("qol_sub_issue", ""),
            "qol_verbatim":        f.get("qol_verbatim", ""),
            "_has_finding": True,
            "_finding_index": i,
            "_finding_count": len(findings),
            "rationale": rationale,
        })
    return out


REPORT_TYPE = ReportType(
    id="pharma_social_intelligence",
    name="Pharma Social Intelligence",
    description="Disease-area patient/caregiver insight tagging. Multi-finding output (1 post → 0..N rows) across Stage, Theme, Unmet Need, Concern, and QoL Impact dimensions.",
    schema=PharmaSIAnalysis,
    system_prompt=PHARMA_SI_SYSTEM_PROMPT,
    post_processor=_pharma_si_post_processor,
)
