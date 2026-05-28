"""
FastAPI router for the agentic orchestrator endpoint.

Provides a streaming POST /orchestrate endpoint that invokes the orchestrator
and returns JSON-lines (one per thinking step / tool call / result).
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from orchestrator import run_orchestrator

log = logging.getLogger("e_ai.orchestrator_endpoint")

router = APIRouter(tags=["orchestrator"])


class OrchestratePayload(BaseModel):
    session_id: str
    prompt: str
    provider: str = Field(default="claude", description="LLM provider to use for the orchestrator.")
    inspect_mode: bool = Field(
        default=False,
        description="When true, the orchestrator pauses after each tool call for user approval.",
    )


class ContinuePayload(BaseModel):
    action: str = Field(..., description='"approve" or "refine".')
    feedback: Optional[str] = Field(default=None, description="Feedback when refining.")


@router.post("/orchestrate")
async def orchestrate(payload: OrchestratePayload):
    """
    Run the agentic orchestrator on a session.

    Streams JSON-lines back to the client. Each line is a JSON object with
    a "type" field:
      - "thinking"    — the orchestrator's reasoning text
      - "tool_call"   — a tool invocation (name + args)
      - "tool_result" — the result of a tool call
      - "complete"    — final result with report and summary
      - "error"       — an error occurred
    """
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not payload.prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    log.info(
        f"Orchestrate request: session={payload.session_id} "
        f"provider={payload.provider} prompt={payload.prompt[:100]}..."
    )

    async def event_stream():
        try:
            async for event_line in run_orchestrator(
                session_id=payload.session_id,
                user_prompt=payload.prompt,
                provider=payload.provider,
                inspect_mode=payload.inspect_mode,
            ):
                yield event_line
        except Exception as e:
            log.error(f"Orchestrator stream error: {e}")
            yield json.dumps({
                "type": "error",
                "text": f"Stream error: {str(e)[:300]}",
            }) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/orchestrate/{session_id}/continue")
async def orchestrate_continue(session_id: str, payload: ContinuePayload):
    """
    Signal a paused inspect-mode orchestrator to continue.

    Body: {action: "approve"|"refine", feedback?: string}
    - "approve" → continue to the next tool
    - "refine"  → re-run the current sub-agent with the feedback in context
    """
    if payload.action not in ("approve", "refine"):
        raise HTTPException(status_code=400, detail='action must be "approve" or "refine"')

    # Lazy import to avoid circulars
    import main as _main

    try:
        session = _main.get_session(session_id)
    except HTTPException:
        raise

    pending = session.get("pending_checkpoint")
    if not pending or not pending.get("waiting"):
        raise HTTPException(status_code=409, detail="No checkpoint is currently waiting for approval.")

    updated = {
        **pending,
        "waiting": False,
        "action": payload.action,
        "feedback": payload.feedback or "",
    }
    _main.update_session(session_id, {"pending_checkpoint": updated})

    return {
        "status": "ok",
        "action": payload.action,
        "tool": pending.get("tool_name"),
    }
