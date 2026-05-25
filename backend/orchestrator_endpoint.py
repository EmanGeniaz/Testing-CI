"""
FastAPI router for the agentic orchestrator endpoint.

Provides a streaming POST /orchestrate endpoint that invokes the orchestrator
and returns JSON-lines (one per thinking step / tool call / result).
"""

import asyncio
import json
import logging

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
