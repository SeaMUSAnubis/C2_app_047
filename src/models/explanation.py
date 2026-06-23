from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SuspiciousURLInput(BaseModel):
    url: str
    domain: str | None = None
    reason: str | None = None
    risk_score: float | None = Field(default=None, ge=0, le=100)


class TimelineEventInput(BaseModel):
    event_id: str
    timestamp: datetime | str
    event_type: str
    description: str
    device_id: str | None = None
    source_file: str | None = None
    risk_marker: bool = False


class BaselineComparisonInput(BaseModel):
    feature_name: str
    current_value: float | int | str | None = None
    baseline_value: float | int | str | None = None
    deviation: float | None = None
    unit: str | None = None


class AnomalyFeatureInput(BaseModel):
    feature_name: str
    feature_value: float | int | str | None = None
    contribution_score: float | None = None
    description: str | None = None


class AlertExplanationRequest(BaseModel):
    alert_id: str
    user_id: str
    device_id: str | None = None

    risk_score: float = Field(ge=0, le=100)
    severity: Literal["low", "medium", "high", "critical"]
    alert_status: Literal[
        "new",
        "investigating",
        "resolved",
        "false_positive",
    ]

    anomaly_score: float | None = None
    reconstruction_error: float | None = None
    threshold: float | None = None
    model_name: str | None = None
    model_version: str | None = None

    main_reason: str | None = None
    anomalous_features: list[AnomalyFeatureInput] = []
    baseline_comparisons: list[BaselineComparisonInput] = []
    timeline_events: list[TimelineEventInput] = []
    suspicious_urls: list[SuspiciousURLInput] = []

    additional_context: dict[str, Any] = {}


class ExplanationEvidence(BaseModel):
    evidence_type: Literal[
        "anomalous_feature",
        "baseline_deviation",
        "timeline_event",
        "suspicious_url",
        "risk_score",
        "model_output",
    ]

    description: str
    source_reference: str | None = None


class RecommendedAction(BaseModel):
    action: str
    priority: Literal["low", "medium", "high"]
    requires_human_approval: bool = True


class AlertExplanationResponse(BaseModel):
    alert_id: str

    summary: str

    why_suspicious: list[str]

    evidence: list[ExplanationEvidence]

    baseline_comparison: str | None = None

    recommended_actions: list[RecommendedAction]

    suspicious_domains: list[str] = []

    confidence: float = Field(ge=0, le=1)

    limitations: list[str] = []

    generated_by: Literal["llm", "rule_based"]

    model_name: str | None = None
    prompt_version: str

    risk_score: float = Field(ge=0, le=100)
    severity: Literal["low", "medium", "high", "critical"]

    safety_flags: list[str] = []

    generated_at: datetime
    trace_id: str
    evidence_hash: str | None = None

