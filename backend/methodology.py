"""
Methodology Integration — InfoVision CI Research Methodology.

Encodes the complete 13-step consumer intelligence research methodology
so the orchestrator can reference structured workflow guidance at each
stage of analysis.

Based on: "Step-by-Step Process for Conducting a Social Media Intelligence /
Consumer Intelligence Report" — the enterprise-grade CI research workflow.
"""

from __future__ import annotations

METHODOLOGY: dict = {
    "name": "InfoVision CI Research Methodology",
    "version": "1.0",
    "summary": (
        "A structured research workflow that converts unstructured online "
        "conversations into business decisions, opportunity areas, risks, "
        "and strategic recommendations. Not just social listening — this is "
        "enterprise-grade consumer intelligence."
    ),
    "steps": [
        {
            "id": 1,
            "name": "Define Business Objective",
            "description": (
                "Frame the business problem clearly. Determine: What decision "
                "will this report support? Who is the audience (CMO, Insights, "
                "Product, Innovation, CX, Reputation/Comms)? What category or "
                "problem is being studied? What geography, language, and time "
                "period? What competitors are relevant? What consumer cohorts "
                "matter? What output is expected (dashboard, executive report, "
                "trend analysis, opportunity mapping, narrative intelligence, "
                "innovation recommendations)?"
            ),
            "agent_action": "Extract from user prompt",
        },
        {
            "id": 2,
            "name": "Develop Research Framework",
            "description": (
                "Before collecting data, define hypotheses, themes, research "
                "dimensions, KPIs, and coding structure. This is the 'study "
                "architecture.' Build research pillars: keywords (brand names, "
                "competitors, misspellings, hashtags, product names, slang), "
                "boolean logic for queries, and a taxonomy framework that "
                "becomes the coding backbone."
            ),
            "agent_action": "Build taxonomy from skill",
        },
        {
            "id": 3,
            "name": "Identify Data Sources",
            "description": (
                "Not all platforms serve the same purpose. Different objectives "
                "require different source mixes. Examples: Luxury brand needs "
                "Instagram + TikTok + Reddit; Pharma needs Reddit + Patient "
                "Forums + X; Retail app needs App Store + Reddit + X. Select "
                "from social platforms and non-social sources."
            ),
            "agent_action": "Check available connectors",
        },
        {
            "id": 4,
            "name": "Data Extraction",
            "description": (
                "Collect the raw conversation data via social listening "
                "platforms, APIs, or web scraping. Capture key metadata "
                "alongside the raw text."
            ),
            "agent_action": "Upload or API pull",
        },
        {
            "id": 5,
            "name": "Data Cleaning",
            "description": (
                "Raw social data is messy — usually 30-60% is noise. Remove "
                "spam, bots, duplicate posts, promotions, news reposts, "
                "irrelevant mentions, stock/investor discussions, recruitment "
                "mentions, and fake engagement. Normalize emojis, slang, "
                "misspellings, short forms, language variations. Deduplicate "
                "to prevent viral reposts from distorting volume. Validate "
                "relevance through manual sample review."
            ),
            "agent_action": "Run _cleanse_data",
        },
        {
            "id": 6,
            "name": "Coding & Classification",
            "description": (
                "Convert raw text into analyzable datasets. Add structured "
                "layers: Sentiment (Positive/Negative/Neutral/Mixed), Emotion "
                "(Frustration/Joy/Anxiety/Trust/Excitement/Disappointment), "
                "Topic Tags, Consumer Personas, Intent Classification "
                "(Complaint/Recommendation/Purchase intent/Comparison/"
                "Advocacy/Churn risk)."
            ),
            "agent_action": "Run tagging with selected skill",
        },
        {
            "id": 7,
            "name": "Data Contextualization",
            "description": (
                "Raw mentions are meaningless without context. Ask: Why is "
                "this conversation happening? What external events triggered "
                "spikes? Is this seasonal, culturally driven, tied to "
                "competitors, influencer/amplified behavior, or a long-term "
                "trend? Combine social data with market news, product "
                "launches, ad campaigns, economic events, regulatory updates, "
                "viral moments, and competitor activity."
            ),
            "agent_action": "Cross-reference with context",
        },
        {
            "id": 8,
            "name": "Analytical Modeling",
            "description": (
                "Systematically analyze the data using manual coding, "
                "AI-assisted classification, NLP-based thematic analysis, "
                "or hybrid human + AI analysis."
            ),
            "agent_action": "Pattern analysis",
        },
        {
            "id": 9,
            "name": "Core Analysis",
            "description": (
                "Five core analysis layers: "
                "A) Volume Analysis — mention growth, conversation spikes, "
                "share of voice, platform contribution. "
                "B) Sentiment Analysis — overall, by topic, by competitor, "
                "by geography. "
                "C) Narrative Analysis — dominant, emerging, conflicting, "
                "advocacy, and misinformation narratives. "
                "D) Theme & Topic Analysis — cluster conversations into "
                "needs, pain points, motivations, expectations, use cases. "
                "E) Audience/Persona Analysis — who drives conversations, "
                "who is most dissatisfied, who is growing."
            ),
            "agent_action": "Run analyze_patterns",
        },
        {
            "id": 10,
            "name": "Insight Generation",
            "description": (
                "An insight explains: What is happening, Why it matters, "
                "Business implication, and Recommended action. "
                "Weak: 'Consumers complain about delivery delays.' "
                "Strong: 'Delivery frustration is not driven by speed alone "
                "— consumers increasingly interpret unpredictable delivery "
                "timelines as a signal of poor operational reliability, "
                "leading to trust erosion and competitor switching.'"
            ),
            "agent_action": "LLM report generation",
        },
        {
            "id": 11,
            "name": "KPI Measurement",
            "description": (
                "Quantify findings into measurable business indicators. "
                "Common Consumer Intelligence KPIs include share of voice, "
                "sentiment ratios, engagement rates, advocacy scores, "
                "churn risk indicators, and brand health metrics."
            ),
            "agent_action": "Compute metrics",
        },
        {
            "id": 12,
            "name": "Report Development",
            "description": (
                "Structure the report for the target audience. Select the "
                "appropriate template. Organize findings by priority and "
                "impact. Ensure data visualizations are clear and compelling."
            ),
            "agent_action": "Use template + storyboarding",
        },
        {
            "id": 13,
            "name": "Storytelling",
            "description": (
                "This is where most intelligence projects fail. Insights "
                "must be: Structured, Prioritized, Visual, and "
                "Executive-friendly. Apply cinematic narrative structure "
                "with hero sections, clear section flow, evidence modals, "
                "and actionable recommendations."
            ),
            "agent_action": "Apply storyboarding skill",
        },
    ],
}


OPERATIONAL_WORKFLOW: dict = {
    "name": "InfoVision Operational Research Workflow",
    "version": "1.0",
    "author": "Monisha",
    "summary": (
        "The 19-step operational project lifecycle for conducting consumer "
        "intelligence research — from the initial client ask through to "
        "final human validation of the delivered report."
    ),
    "steps": [
        {"id": 1, "name": "The Ask", "objective": "Understand what the client wants to learn or solve.", "activities": "Stakeholder discussions, requirement gathering, defining KPIs and research objectives, understanding expected outputs.", "outputs": "Research brief, scope document, initial assumptions and success criteria.", "agent_action": "Extract the business question, audience, geography, timeframe, and deliverable type from the user prompt."},
        {"id": 2, "name": "Feasibility Check", "objective": "Confirm the required data exists and can be collected accurately.", "activities": "Check data availability, expected volume, geographic/language coverage, platform accessibility, timeline feasibility, compliance.", "outputs": "Go/No-Go decision, initial methodology recommendation, estimated effort.", "agent_action": "Analyze the uploaded data or check available API connectors. Report feasibility."},
        {"id": 3, "name": "Create Search Query for Testing", "objective": "Measure how much relevant data exists before scaling.", "activities": "Build preliminary keyword/search logic, test Boolean operators, pull small data samples, evaluate signal vs noise.", "outputs": "Test query, preliminary dataset, relevancy observations.", "agent_action": "If data is uploaded, sample and assess relevancy. If using APIs, construct test queries."},
        {"id": 4, "name": "Human Check", "objective": "Ensure retrieved data aligns with research expectations.", "activities": "Review sampled records manually, check contextual accuracy, identify false positives/negatives, validate terminology.", "outputs": "Human-approved query adjustments, refinement recommendations.", "agent_action": "Present a data quality summary and sample rows for the user to validate."},
        {"id": 5, "name": "Validation Sign-off", "objective": "Confirm methodology and sample outputs meet expectations.", "activities": "Stakeholder sign-off, finalize project scope and methodology.", "outputs": "Approved research framework, green light for execution.", "agent_action": "Wait for user confirmation before proceeding to full analysis."},
        {"id": 6, "name": "Project Begins", "objective": "Initiate full-scale workflow execution.", "activities": "Assign responsibilities, create timelines, set up QA processes.", "outputs": "Project plan, workflow structure.", "agent_action": "Initialize the analysis pipeline with confirmed parameters."},
        {"id": 7, "name": "Create Master Search Query", "objective": "Capture the most relevant and comprehensive dataset.", "activities": "Expand keyword taxonomy, add Boolean logic, include exclusions and refinements.", "outputs": "Master search query, query documentation.", "agent_action": "Use the full dataset with confirmed schema and filtering."},
        {"id": 8, "name": "Download Sample Data", "objective": "Validate production query before full extraction.", "activities": "Pull representative sample, export structured files, verify metadata consistency.", "outputs": "Sample dataset, export files.", "agent_action": "Extract and present a sample for review."},
        {"id": 9, "name": "Share Sample for Relevancy Check", "objective": "Confirm data accurately reflects research objectives.", "activities": "Share sample outputs, collect feedback, discuss edge cases.", "outputs": "Relevancy feedback, adjustment requests.", "agent_action": "Show sample results to user for approval."},
        {"id": 10, "name": "Lock Methodology", "objective": "Lock methodology before large-scale processing.", "activities": "Approval of sampled dataset and extraction logic.", "outputs": "Approved data collection framework, sign-off for tagging.", "agent_action": "Confirm skill/report type selection with user."},
        {"id": 11, "name": "Tagging with Sample Data", "objective": "Develop and test the tagging framework.", "activities": "Create tagging taxonomy, define sentiment/themes/categories, train models, create coding guidelines.", "outputs": "Tagging schema, tagged sample dataset.", "agent_action": "Run tagging on sample data using selected skill."},
        {"id": 12, "name": "Tagging QA", "objective": "Ensure consistency and accuracy in tagged data.", "activities": "QA checks, inter-coder reliability, resolve ambiguous classifications.", "outputs": "Clean tagged dataset, final analytical dataset.", "agent_action": "Run self_review tool to validate tagging quality."},
        {"id": 13, "name": "Start Analysis", "objective": "Identify patterns, trends, opportunities, and risks.", "activities": "Quantitative analysis, qualitative analysis, trend identification, segmentation, comparative analysis.", "outputs": "Insight summaries, analytical findings, key observations.", "agent_action": "Run analyze_patterns tool on tagged data."},
        {"id": 14, "name": "Create KPI Charts", "objective": "Convert insights into easy-to-understand visuals.", "activities": "Build dashboards and charts, highlight trends and benchmarks, visual storytelling.", "outputs": "KPI dashboards, visual charts and graphs.", "agent_action": "Generate report with KPI cards, bar charts, journey maps."},
        {"id": 15, "name": "Start Report Writing", "objective": "Communicate insights clearly and strategically.", "activities": "Write executive summary, develop methodology section, explain findings and recommendations, integrate charts.", "outputs": "Draft report, insight narratives.", "agent_action": "Generate narrative report using storyboarding skill."},
        {"id": 16, "name": "Share Draft Report", "objective": "Collect stakeholder feedback before finalization.", "activities": "Export report files, share internally, gather comments and revision requests.", "outputs": "Shared draft report, stakeholder feedback.", "agent_action": "Present report to user for review via the refine panel."},
        {"id": 17, "name": "Design the Report", "objective": "Create a polished and client-ready deliverable.", "activities": "Apply branding, improve layout and formatting, refine visual hierarchy, optimize readability.", "outputs": "Designed final report, presentation-ready assets.", "agent_action": "Apply design skill (template selection, branding, storyboarding)."},
        {"id": 18, "name": "Approve Design", "objective": "Ensure branding, formatting, and presentation meet expectations.", "activities": "Review visuals and formatting, final correction cycle, final sign-off.", "outputs": "Approved final report.", "agent_action": "Present final report for user approval."},
        {"id": 19, "name": "Human Validation", "objective": "Ensure accuracy, consistency, and credibility.", "activities": "Final manual QA, cross-checking numbers, fact validation, consistency review.", "outputs": "Final validated deliverables, client-ready research package.", "agent_action": "Present validation summary. Export final HTML/PPTX/CSV."},
    ],
}


def get_methodology() -> dict:
    """Return both methodologies."""
    return {
        "analytical": METHODOLOGY,
        "operational": OPERATIONAL_WORKFLOW,
    }


def get_methodology_steps() -> list[dict]:
    """Return just the list of methodology steps."""
    return METHODOLOGY["steps"]


def get_methodology_for_orchestrator() -> str:
    """Return methodology as a text prompt the orchestrator can use.

    Formats the 13-step methodology into structured instructions that
    an LLM orchestrator can follow during analysis.
    """
    lines: list[str] = []
    lines.append(f"## {METHODOLOGY['name']} (v{METHODOLOGY['version']})")
    lines.append("")
    lines.append(METHODOLOGY["summary"])
    lines.append("")
    lines.append("Follow these 13 steps in order. You may skip steps that "
                 "are not applicable, but always consider each one.")
    lines.append("")

    for step in METHODOLOGY["steps"]:
        lines.append(
            f"### Step {step['id']}: {step['name']}"
        )
        lines.append(f"**What:** {step['description']}")
        lines.append(f"**Your action:** {step['agent_action']}")
        lines.append("")

    lines.append(
        "Remember: A strong consumer intelligence report is not just "
        "'social listening.' It is a structured research workflow that "
        "converts unstructured online conversations into business decisions, "
        "opportunity areas, risks, and strategic recommendations."
    )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## {OPERATIONAL_WORKFLOW['name']} (v{OPERATIONAL_WORKFLOW['version']})")
    lines.append("")
    lines.append(OPERATIONAL_WORKFLOW["summary"])
    lines.append("")
    lines.append("This is the operational project lifecycle. Follow these steps "
                 "to ensure rigour and quality at every stage.")
    lines.append("")

    for step in OPERATIONAL_WORKFLOW["steps"]:
        lines.append(f"### Step {step['id']}: {step['name']}")
        lines.append(f"**Objective:** {step['objective']}")
        lines.append(f"**Activities:** {step['activities']}")
        lines.append(f"**Outputs:** {step['outputs']}")
        lines.append(f"**Your action:** {step['agent_action']}")
        lines.append("")

    return "\n".join(lines)
