"""Base contracts for pluggable report types.

A ReportType bundles everything needed to run the tagging pipeline against a
specific methodology: the Pydantic output schema, the system prompt template,
and an optional post-processor for report types that emit multiple findings
per input row (e.g. Pharma Social Intelligence).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel


PostProcessor = Callable[[dict, dict], list[dict]]
"""Takes (raw_input_row, parsed_llm_output_dict) and returns a list of output
rows. Default behaviour merges them into a single row. Multi-finding report
types (Pharma SI) can return N rows from one input."""


def default_post_processor(raw_row: dict, parsed: dict) -> list[dict]:
    """1:1 merge of raw input columns + parsed LLM output."""
    return [{**raw_row, **parsed}]


@dataclass(frozen=True)
class ReportType:
    """One methodology bundled as code.

    id: stable string used in API payloads (snake_case, no spaces).
    name: human-readable label for the UI dropdown.
    description: one-line description for the UI.
    schema: Pydantic model the LLM is asked to fill in.
    system_prompt: prompt template. Must include the variables documented
        below (see explainable_ai_tagging.py for the canonical example).
    prompt_variables: list of variable names the prompt template references,
        excluding format_instructions which is supplied automatically.
    post_processor: optional fn to fan out one input row into N output rows.
    """

    id: str
    name: str
    description: str
    schema: Type[BaseModel]
    system_prompt: str
    prompt_variables: list[str] = field(default_factory=lambda: [
        "brand_focus", "dataset_type", "additional_context", "source_text",
    ])
    post_processor: PostProcessor = default_post_processor
