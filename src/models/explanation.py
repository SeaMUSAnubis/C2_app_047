"""Compatibility exports for the legacy LLM explanation service.

The canonical schemas live under `src.backend.app.schemas.explanation`.
Older evaluation and guardrail modules still import from `src.models.explanation`,
so this module keeps those imports working without duplicating model definitions.
"""

from src.backend.app.schemas.explanation import (
    AlertExplanationRequest,
    AlertExplanationResponse,
    AnomalyFeatureInput,
    BaselineComparisonInput,
    ExplanationEvidence,
    RecommendedAction,
    SuspiciousURLInput,
    TimelineEventInput,
)

SuspiciousUrlInput = SuspiciousURLInput

__all__ = [
    "AlertExplanationRequest",
    "AlertExplanationResponse",
    "AnomalyFeatureInput",
    "BaselineComparisonInput",
    "ExplanationEvidence",
    "RecommendedAction",
    "SuspiciousURLInput",
    "SuspiciousUrlInput",
    "TimelineEventInput",
]

