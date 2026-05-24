"""Registry of available report types.

Add a new report type by importing its REPORT_TYPE constant here and adding
it to _REPORT_TYPES. The id must be unique and stable (it's used in API
payloads and persisted to runs.json).
"""

from .base import ReportType
from .explainable_ai_tagging import REPORT_TYPE as EXPLAINABLE_AI_TAGGING
from .pharma_social_intelligence import REPORT_TYPE as PHARMA_SOCIAL_INTELLIGENCE
from .genz_brand_tracker import REPORT_TYPE as GENZ_BRAND_TRACKER


_REPORT_TYPES: dict[str, ReportType] = {
    EXPLAINABLE_AI_TAGGING.id:     EXPLAINABLE_AI_TAGGING,
    PHARMA_SOCIAL_INTELLIGENCE.id: PHARMA_SOCIAL_INTELLIGENCE,
    GENZ_BRAND_TRACKER.id:         GENZ_BRAND_TRACKER,
}

DEFAULT_REPORT_TYPE_ID = EXPLAINABLE_AI_TAGGING.id


def list_report_types() -> list[dict]:
    """JSON-serialisable summary for the frontend dropdown."""
    return [
        {"id": rt.id, "name": rt.name, "description": rt.description}
        for rt in _REPORT_TYPES.values()
    ]


def get_report_type(report_type_id: str) -> ReportType:
    if report_type_id not in _REPORT_TYPES:
        raise KeyError(
            f"Unknown report_type '{report_type_id}'. Available: {list(_REPORT_TYPES)}"
        )
    return _REPORT_TYPES[report_type_id]
