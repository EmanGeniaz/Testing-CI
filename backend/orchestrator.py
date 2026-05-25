"""
Agentic orchestrator for the Consumer Intelligence platform.

Uses the Anthropic SDK directly with tool_use to implement a ReAct-style
(Think → Act → Observe) loop. Claude Opus reasons about which pipeline
steps to run, calls them as tools, observes results, and decides next steps.

Tools wrap the existing pipeline functions (cleanse, tag, analyze, report)
so no logic is duplicated.
"""

import os
import json
import time
import uuid
import logging
import traceback
from typing import AsyncGenerator, Optional
from datetime import datetime
from pathlib import Path

import anthropic

from report_types import list_report_types, get_report_type, DEFAULT_REPORT_TYPE_ID

log = logging.getLogger("e_ai.orchestrator")

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS — import what we need from main without circular deps
# ═══════════════════════════════════════════════════════════════════════════════

# Lazy imports from main to avoid circular import at module level.
# These are resolved on first call inside each tool function.


def _get_main():
    """Return the main module (imported lazily)."""
    import main as _main
    return _main


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL DEFINITIONS (for the Anthropic tool_use API)
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    {
        "name": "analyze_data_quality",
        "description": (
            "Examine the uploaded data for a session. Returns column names, "
            "row count, sample rows, data types, missing-value counts, and "
            "quality issues. Call this first to understand what data is available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID whose data to examine.",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "select_skill",
        "description": (
            "Pick the best existing skill (report type / tagging methodology) "
            "for the user's task. Returns the selected skill ID, name, and "
            "description, or recommends creating a custom schema if none fit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID (for context about the data).",
                },
                "task_description": {
                    "type": "string",
                    "description": "What the user wants to accomplish — used to match against available skills.",
                },
            },
            "required": ["session_id", "task_description"],
        },
    },
    {
        "name": "create_custom_schema",
        "description": (
            "When no existing skill fits, construct a custom tagging schema "
            "based on the user's requirements. Returns a schema definition "
            "that can be used for tagging."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID.",
                },
                "schema_description": {
                    "type": "string",
                    "description": "Natural language description of what fields/tags the schema should have.",
                },
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["string", "integer", "float", "boolean"]},
                            "description": {"type": "string"},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "If categorical, the allowed values.",
                            },
                        },
                        "required": ["name", "type", "description"],
                    },
                    "description": "List of fields the custom schema should contain.",
                },
            },
            "required": ["session_id", "schema_description", "fields"],
        },
    },
    {
        "name": "clean_data",
        "description": (
            "Run the data cleansing pipeline on the session's raw data. "
            "Removes duplicates, empty rows, and noise. Returns cleaning "
            "statistics (original count, cleaned count, removals by type)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID whose data to clean.",
                },
                "text_column": {
                    "type": "string",
                    "description": "The primary text column to use for deduplication and quality checks.",
                },
            },
            "required": ["session_id", "text_column"],
        },
    },
    {
        "name": "run_tagging",
        "description": (
            "Trigger the tagging engine on session data using a specific skill "
            "(report type). The session must have schema_config and dataset_context "
            "set. This starts the tagging process and polls until it completes. "
            "Returns the final status and row counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to tag.",
                },
                "report_type_id": {
                    "type": "string",
                    "description": "The report type / skill ID to use for tagging.",
                },
                "text_column": {
                    "type": "string",
                    "description": "The primary text column to analyze.",
                },
                "ai_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional columns to include as context for the AI.",
                },
                "focus_brand": {
                    "type": "string",
                    "description": "The brand or entity to focus on (optional).",
                    "default": "",
                },
                "dataset_type": {
                    "type": "string",
                    "description": "Type of dataset (e.g., 'Single brand', 'Multi-brand', 'Industry').",
                    "default": "Mixed / unknown",
                },
                "additional_context": {
                    "type": "string",
                    "description": "Any extra context about the dataset.",
                    "default": "",
                },
            },
            "required": ["session_id", "report_type_id", "text_column"],
        },
    },
    {
        "name": "analyze_patterns",
        "description": (
            "Analyze tagged data for patterns, themes, anomalies, and key "
            "statistics. Returns theme distribution, sentiment breakdown, "
            "signal counts, and notable patterns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID with completed tagging.",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Generate a narrative report from tagged data. Creates an executive "
            "summary with findings, evidence, and recommendations. Returns the "
            "full report structure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID with completed tagging.",
                },
                "focus_area": {
                    "type": "string",
                    "description": "Optional area to focus the report on (e.g., 'sentiment trends', 'brand risks').",
                    "default": "",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "self_review",
        "description": (
            "Review the orchestrator's own output for quality, evidence "
            "strength, and gaps. Returns a quality assessment with suggestions "
            "for improvement."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to review.",
                },
                "report_summary": {
                    "type": "string",
                    "description": "Summary of the report generated so far.",
                },
                "findings_count": {
                    "type": "integer",
                    "description": "Number of findings in the report.",
                },
                "evidence_count": {
                    "type": "integer",
                    "description": "Number of evidence items in the report.",
                },
            },
            "required": ["session_id", "report_summary", "findings_count", "evidence_count"],
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _tool_analyze_data_quality(session_id: str) -> dict:
    """Examine uploaded data quality for a session."""
    m = _get_main()
    session = m.get_session(session_id)

    raw_data = session.get("raw_data", [])
    columns = session.get("columns", [])
    preview = session.get("preview", [])
    filename = session.get("filename", "unknown")

    # Column-level quality analysis
    col_info = []
    for col in columns:
        values = [row.get(col) for row in raw_data]
        non_null = [v for v in values if v is not None and str(v).strip()]
        unique_count = len(set(str(v) for v in non_null))

        # Detect likely text columns (high cardinality, longer strings)
        avg_len = 0
        if non_null:
            avg_len = sum(len(str(v)) for v in non_null) / len(non_null)

        col_info.append({
            "name": col,
            "non_null_count": len(non_null),
            "null_count": len(values) - len(non_null),
            "unique_values": unique_count,
            "avg_length": round(avg_len, 1),
            "is_likely_text": avg_len > 50,
            "sample_values": [str(v)[:100] for v in non_null[:3]],
        })

    # Overall quality issues
    issues = []
    total_rows = len(raw_data)
    if total_rows == 0:
        issues.append("Dataset is empty — no rows found.")
    for ci in col_info:
        if ci["null_count"] > total_rows * 0.5:
            issues.append(f"Column '{ci['name']}' is >50% empty ({ci['null_count']}/{total_rows} null).")
        if ci["unique_values"] == 1 and ci["non_null_count"] > 1:
            issues.append(f"Column '{ci['name']}' has only one unique value — may not be useful for analysis.")

    # Suggest primary text column
    text_candidates = sorted(
        [c for c in col_info if c["is_likely_text"]],
        key=lambda c: c["avg_length"],
        reverse=True,
    )
    suggested_text_col = text_candidates[0]["name"] if text_candidates else (columns[0] if columns else "")

    return {
        "filename": filename,
        "row_count": total_rows,
        "column_count": len(columns),
        "columns": col_info,
        "preview": preview[:3],
        "quality_issues": issues,
        "suggested_text_column": suggested_text_col,
    }


def _tool_select_skill(session_id: str, task_description: str) -> dict:
    """Select the best existing skill for the task."""
    available = list_report_types()

    # Return available skills with a recommendation
    return {
        "available_skills": available,
        "task_description": task_description,
        "recommendation": (
            "Choose the skill whose description best matches the task. "
            "If none fit well, use create_custom_schema to build a tailored schema."
        ),
    }


def _tool_create_custom_schema(session_id: str, schema_description: str, fields: list) -> dict:
    """Create a custom tagging schema definition."""
    schema_id = f"custom_{uuid.uuid4().hex[:8]}"

    schema_def = {
        "id": schema_id,
        "description": schema_description,
        "fields": fields,
    }

    # Store the custom schema in the session for reference
    m = _get_main()
    m.update_session(session_id, {"custom_schema": schema_def})

    return {
        "schema_id": schema_id,
        "description": schema_description,
        "field_count": len(fields),
        "fields": fields,
        "note": (
            "Custom schema created. However, the tagging engine currently "
            "requires a registered report type. Use an existing report type "
            "for tagging or extend the registry. The custom schema has been "
            "saved to the session for reference."
        ),
    }


def _tool_clean_data(session_id: str, text_column: str) -> dict:
    """Run data cleansing pipeline."""
    m = _get_main()
    session = m.get_session(session_id)
    raw_data = session.get("raw_data", [])

    if not raw_data:
        return {"error": "No raw data in session."}

    cleaned_data, stats = m._cleanse_data(raw_data, text_column)

    # Update session with cleaned data
    m.update_session(session_id, {"raw_data": cleaned_data})
    log.info(f"Orchestrator cleaned data for {session_id}: {stats}")

    return {
        "status": "success",
        "stats": stats,
        "message": (
            f"Cleaned {stats['original']} rows → {stats['cleaned']} rows. "
            f"Removed {stats['removed_duplicates']} duplicates, "
            f"{stats['removed_empty']} empty, {stats['removed_noise']} noise."
        ),
    }


def _tool_run_tagging(
    session_id: str,
    report_type_id: str,
    text_column: str,
    ai_columns: Optional[list] = None,
    focus_brand: str = "",
    dataset_type: str = "Mixed / unknown",
    additional_context: str = "",
) -> dict:
    """Set up session and run the tagging pipeline synchronously."""
    m = _get_main()

    # Validate report type
    try:
        get_report_type(report_type_id)
    except KeyError as e:
        return {"error": str(e)}

    # Set dataset context
    m.update_session(session_id, {
        "dataset_context": {
            "focus_brand": focus_brand,
            "dataset_type": dataset_type,
            "additional_context": additional_context,
        },
    })

    # Set schema config
    m.update_session(session_id, {
        "schema_config": {
            "primary_text_column": text_column,
            "visible_columns": [],
            "ai_columns": ai_columns or [text_column],
        },
    })

    # Create a run ID and prepare session
    run_id = str(uuid.uuid4())[:8]
    session = m.get_session(session_id)

    m.update_session(session_id, {
        "status": "running",
        "analyzed_data": [],
        "progress": 0,
        "run_id": run_id,
        "report_type": report_type_id,
    })

    # Re-fetch session after updates
    session = m.get_session(session_id)

    log.info(f"Orchestrator starting tagging run {run_id} for session {session_id}")

    # Run tagging synchronously (blocking) — the orchestrator will wait for it
    try:
        m._run_tagging_bg(
            session_id=session_id,
            provider="claude",
            api_key="",
            model=None,
            session=session,
            run_id=run_id,
            report_type_id=report_type_id,
        )
    except Exception as e:
        log.error(f"Tagging run {run_id} failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "error",
            "run_id": run_id,
            "error": str(e)[:500],
        }

    # Fetch final status
    session = m.get_session(session_id)
    analyzed_data = session.get("analyzed_data", [])
    status = session.get("status", "unknown")

    return {
        "status": status,
        "run_id": run_id,
        "total_rows_tagged": len(analyzed_data),
        "error_rows": sum(1 for r in analyzed_data if r.get("error")),
        "message": f"Tagging complete: {len(analyzed_data)} rows tagged (status={status}).",
    }


def _tool_analyze_patterns(session_id: str) -> dict:
    """Analyze tagged data for patterns and statistics."""
    m = _get_main()
    session = m.get_session(session_id)
    analyzed_data = session.get("analyzed_data", [])

    if not analyzed_data:
        return {"error": "No analyzed data available. Run tagging first."}

    stats = m._collect_tag_stats(analyzed_data)
    stats_text = m._build_stats_text(stats)

    # Build a summary
    total = stats["total_rows"]
    errors = stats["error_rows"]
    valid = total - errors

    # Top items from each dimension
    def top_items(counter, n=5):
        if not counter:
            return []
        return [{"value": k, "count": v, "pct": round(v / valid * 100, 1) if valid > 0 else 0}
                for k, v in counter.most_common(n)]

    patterns = {
        "total_rows": total,
        "valid_rows": valid,
        "error_rows": errors,
        "top_themes": top_items(stats["themes"]),
        "sentiment_distribution": top_items(stats["sentiments"]),
        "top_emotions": top_items(stats["emotions"]),
        "top_signals": top_items(stats["signals"]),
        "top_drivers": top_items(stats["drivers"]),
        "top_brands": top_items(stats["brands"]),
        "stats_text": stats_text,
    }

    # Add severity/confidence summaries if present
    if stats["severities"]:
        patterns["severity_avg"] = round(sum(stats["severities"]) / len(stats["severities"]), 1)
        patterns["severity_max"] = max(stats["severities"])
    if stats["confidences"]:
        patterns["confidence_avg"] = round(sum(stats["confidences"]) / len(stats["confidences"]), 2)

    # Pharma-specific if present
    if stats["stages"]:
        patterns["disease_stages"] = top_items(stats["stages"])
    if stats["unmet_needs"]:
        patterns["unmet_needs"] = top_items(stats["unmet_needs"])

    return patterns


def _tool_generate_report(session_id: str, focus_area: str = "") -> dict:
    """Generate a narrative report from tagged data."""
    m = _get_main()
    session = m.get_session(session_id)
    analyzed_data = session.get("analyzed_data", [])

    if not analyzed_data:
        return {"error": "No analyzed data available. Run tagging first."}

    # Use the existing report generation logic
    try:
        report_payload = m.GenerateReportPayload()
        report = m.generate_report(session_id, report_payload)

        # If the response is a FastAPI Response, extract the body
        if hasattr(report, "body"):
            report = json.loads(report.body)

        return {
            "status": "success",
            "report": report,
            "message": (
                f"Report generated with {len(report.get('findings', []))} findings "
                f"and {len(report.get('evidence', []))} evidence items."
            ),
        }
    except Exception as e:
        log.warning(f"LLM report generation failed, using fallback: {e}")
        # Fallback to statistical report
        report = m._generate_fallback_report(session, analyzed_data)
        return {
            "status": "success",
            "report": report,
            "message": "Statistical fallback report generated (no LLM available for report synthesis).",
            "method": "statistical_fallback",
        }


def _tool_self_review(session_id: str, report_summary: str,
                      findings_count: int, evidence_count: int) -> dict:
    """Review the orchestrator's own output for quality."""
    issues = []
    suggestions = []

    # Check findings count
    if findings_count == 0:
        issues.append("No findings were generated — the report may be empty or tagging failed.")
        suggestions.append("Re-run tagging or check data quality.")
    elif findings_count < 3:
        issues.append(f"Only {findings_count} findings — report may lack depth.")
        suggestions.append("Consider analyzing more dimensions of the data.")

    # Check evidence count
    if evidence_count == 0:
        issues.append("No evidence items — findings are unsubstantiated.")
        suggestions.append("Ensure tagging produced verbatim evidence quotes.")
    elif evidence_count < findings_count:
        issues.append("Fewer evidence items than findings — some findings may lack support.")

    # Check report summary
    if len(report_summary) < 50:
        issues.append("Report summary is very short — may lack actionable detail.")
        suggestions.append("Consider adding more context about the dataset and analysis.")

    quality_score = "good"
    if len(issues) >= 3:
        quality_score = "poor"
    elif len(issues) >= 1:
        quality_score = "acceptable"

    return {
        "quality_score": quality_score,
        "issues": issues,
        "suggestions": suggestions,
        "recommendation": (
            "No action needed — report quality is good."
            if quality_score == "good"
            else "Consider addressing the issues above before finalizing."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL DISPATCH
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_HANDLERS = {
    "analyze_data_quality": lambda args: _tool_analyze_data_quality(**args),
    "select_skill": lambda args: _tool_select_skill(**args),
    "create_custom_schema": lambda args: _tool_create_custom_schema(**args),
    "clean_data": lambda args: _tool_clean_data(**args),
    "run_tagging": lambda args: _tool_run_tagging(**args),
    "analyze_patterns": lambda args: _tool_analyze_patterns(**args),
    "generate_report": lambda args: _tool_generate_report(**args),
    "self_review": lambda args: _tool_self_review(**args),
}


def _execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool by name and return its result."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return handler(tool_input)
    except Exception as e:
        log.error(f"Tool {tool_name} failed: {e}\n{traceback.format_exc()}")
        return {"error": f"Tool {tool_name} failed: {str(e)[:500]}"}


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

def _build_system_prompt(session_id: str, user_prompt: str) -> str:
    """Build the system prompt for the orchestrator LLM."""

    # Load available skills
    skills = list_report_types()
    skills_text = "\n".join(
        f"  - {s['id']}: {s['name']} — {s['description']}"
        for s in skills
    )

    # Load session data summary
    try:
        m = _get_main()
        session = m.get_session(session_id)
        filename = session.get("filename", "unknown")
        columns = session.get("columns", [])
        row_count = len(session.get("raw_data", []))
        status = session.get("status", "unknown")
        data_summary = (
            f"File: {filename}\n"
            f"Columns: {', '.join(columns)}\n"
            f"Rows: {row_count}\n"
            f"Status: {status}"
        )
    except Exception:
        data_summary = "Session data not yet loaded."

    return f"""You are an expert Consumer Intelligence orchestrator. Your job is to analyze
data and produce actionable insights based on the user's request.

You have access to a set of tools that represent stages of an analysis pipeline.
Use the ReAct pattern: THINK about what to do, ACT by calling a tool, OBSERVE
the result, then THINK again about what to do next.

## Available Skills (Report Types / Tagging Methodologies)
{skills_text}

## Current Session Data
{data_summary}

## Your Workflow
1. First, understand the user's request and the data available.
2. Analyze data quality to understand columns, types, and issues.
3. Select the best skill (report type) for the task, or create a custom schema.
4. Clean the data if needed.
5. Run tagging with the selected skill.
6. Analyze patterns in the tagged data.
7. Generate a report with findings, evidence, and recommendations.
8. Self-review the output for quality and completeness.

## Rules
- Always start by analyzing data quality so you know what columns exist.
- Pick the text column that has the richest content (longest average text).
- Be explicit about your reasoning at each step.
- If a tool fails, reason about what went wrong and try an alternative approach.
- When the task is complete, provide a clear summary of what was found.
- Ground all findings in actual data — never fabricate statistics or quotes.
- The user's prompt may be high-level ("analyze this data") or specific ("find brand risks").
  Adapt your tool usage accordingly.
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR LOOP
# ═══════════════════════════════════════════════════════════════════════════════

async def run_orchestrator(
    session_id: str,
    user_prompt: str,
    provider: str = "claude",
) -> AsyncGenerator:
    """
    Main orchestrator loop. Yields thinking steps as JSON lines for streaming.

    Uses the ReAct pattern:
    1. THINK: What should I do next?
    2. ACT: Call a tool
    3. OBSERVE: Look at the result
    4. Repeat until done
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield json.dumps({
            "type": "error",
            "message": "ANTHROPIC_API_KEY not configured. Cannot run orchestrator.",
        }) + "\n"
        return

    client = anthropic.Anthropic(api_key=api_key)
    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")

    system_prompt = _build_system_prompt(session_id, user_prompt)

    # Initial messages
    messages = [
        {
            "role": "user",
            "content": (
                f"Session ID: {session_id}\n\n"
                f"User Request: {user_prompt}\n\n"
                "Please analyze the data and fulfill this request using the available tools. "
                "Think step by step about what to do."
            ),
        },
    ]

    yield json.dumps({
        "type": "thinking",
        "text": f"Starting orchestrator for session {session_id}...",
    }) + "\n"

    max_iterations = 15
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        log.info(f"Orchestrator iteration {iteration}/{max_iterations} for session {session_id}")

        try:
            response = client.messages.create(
                model=model,
                max_tokens=16384,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
        except anthropic.APIError as e:
            log.error(f"Anthropic API error: {e}")
            yield json.dumps({
                "type": "error",
                "message": f"LLM API error: {str(e)[:300]}",
            }) + "\n"
            return
        except Exception as e:
            log.error(f"Orchestrator LLM call failed: {e}\n{traceback.format_exc()}")
            yield json.dumps({
                "type": "error",
                "message": f"Orchestrator error: {str(e)[:300]}",
            }) + "\n"
            return

        # Process response content blocks
        assistant_content = response.content
        tool_use_blocks = []

        for block in assistant_content:
            if block.type == "text":
                # Emit thinking step
                text = block.text.strip()
                if text:
                    yield json.dumps({
                        "type": "thinking",
                        "text": text,
                    }) + "\n"

            elif block.type == "tool_use":
                tool_use_blocks.append(block)
                # Emit tool call event
                yield json.dumps({
                    "type": "tool_call",
                    "tool": block.name,
                    "args": block.input,
                }) + "\n"

        # If the model stopped without tool use, it's done thinking
        if response.stop_reason == "end_of_turn" and not tool_use_blocks:
            log.info(f"Orchestrator completed for session {session_id} after {iteration} iterations")

            # Try to extract the final report from the session
            try:
                m = _get_main()
                session = m.get_session(session_id)
                analyzed_data = session.get("analyzed_data", [])
                report = None
                if analyzed_data:
                    try:
                        report_payload = m.GenerateReportPayload()
                        report = m.generate_report(session_id, report_payload)
                        if hasattr(report, "body"):
                            report = json.loads(report.body)
                    except Exception:
                        report = m._generate_fallback_report(session, analyzed_data)

                final_text = ""
                for block in assistant_content:
                    if block.type == "text":
                        final_text += block.text

                yield json.dumps({
                    "type": "complete",
                    "report": report,
                    "summary": final_text.strip(),
                    "iterations": iteration,
                }) + "\n"
            except Exception as e:
                log.warning(f"Could not extract final report: {e}")
                final_text = ""
                for block in assistant_content:
                    if block.type == "text":
                        final_text += block.text
                yield json.dumps({
                    "type": "complete",
                    "report": None,
                    "summary": final_text.strip(),
                    "iterations": iteration,
                }) + "\n"
            return

        # If no tool calls and not end_of_turn, something unexpected happened
        if not tool_use_blocks:
            log.warning(f"Orchestrator stop_reason={response.stop_reason} with no tool calls")
            yield json.dumps({
                "type": "complete",
                "report": None,
                "summary": "Orchestrator ended without completing analysis.",
                "iterations": iteration,
            }) + "\n"
            return

        # Execute tool calls and build tool results
        # Add the assistant message to conversation
        messages.append({
            "role": "assistant",
            "content": [_block_to_dict(b) for b in assistant_content],
        })

        tool_results = []
        for tool_block in tool_use_blocks:
            log.info(f"Executing tool: {tool_block.name} with args: {json.dumps(tool_block.input)[:200]}")

            result = _execute_tool(tool_block.name, tool_block.input)

            # Truncate large results to avoid context overflow
            result_str = json.dumps(result, default=str)
            if len(result_str) > 30000:
                result_str = result_str[:30000] + '..."}'
                result = {"truncated": True, "data": result_str}

            yield json.dumps({
                "type": "tool_result",
                "tool": tool_block.name,
                "result": result,
            }) + "\n"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": json.dumps(result, default=str),
            })

        # Add tool results to conversation
        messages.append({
            "role": "user",
            "content": tool_results,
        })

    # Max iterations reached
    yield json.dumps({
        "type": "error",
        "text": f"Orchestrator reached maximum iterations ({max_iterations}) without completing.",
    }) + "\n"


def _block_to_dict(block) -> dict:
    """Convert an Anthropic content block to a plain dict for message history."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    else:
        return {"type": "text", "text": str(block)}
