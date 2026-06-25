from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: str


Role = Literal["admin", "analyst", "security_manager", "employee"]
UserStatus = Literal["active", "locked", "inactive"]
DeviceStatus = Literal["online", "offline", "retired"]


class AccountPublic(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AccountPublic


class AccountCreate(BaseModel):
    email: str
    full_name: str
    role: Role
    password: str


class AccountUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None


class AccountListItem(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: str


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class UserBase(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    department: str | None = None
    job_role: str | None = None
    status: UserStatus = "active"
    risk_score: int = Field(default=0, ge=0, le=100)


class UserCreate(UserBase):
    id: str


class UserUpdate(BaseModel):
    email: str | None = None
    department: str | None = None
    job_role: str | None = None
    status: UserStatus | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)


class UserRead(UserCreate):
    created_at: str
    updated_at: str


class DeviceBase(BaseModel):
    hostname: str
    os: str | None = None
    ip_address: str | None = None
    assigned_user_id: str | None = None
    status: DeviceStatus = "offline"
    risk_score: int = Field(default=0, ge=0, le=100)
    last_seen: str | None = None


class DeviceCreate(DeviceBase):
    id: str


class DeviceUpdate(BaseModel):
    hostname: str | None = None
    os: str | None = None
    ip_address: str | None = None
    assigned_user_id: str | None = None
    status: DeviceStatus | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)
    last_seen: str | None = None


class DeviceRead(DeviceCreate):
    created_at: str
    updated_at: str
    assigned_username: str | None = None
    assigned_user_name: str | None = None


class EventIngest(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str
    source_file: str
    timestamp: str
    user_id: str | None = None
    device_id: str | None = None
    event_type: str
    action: str | None = None
    resource: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class EventRead(EventIngest):
    id: int
    created_at: str


RawLogEventType = Literal[
    "logon",
    "device",
    "file",
    "http",
    "email",
    "process",
    "network",
    "ldap",
    "psychometric",
    "custom",
]
Severity = Literal["low", "medium", "high", "critical"]
ModelPrediction = Literal["normal", "anomaly"]
AlertStatus = Literal["new", "investigating", "resolved", "false_positive"]


class AlertBase(BaseModel):
    user_id: str | None = None
    device_id: str | None = None
    event_log_id: int | None = None
    model_version: str | None = None
    title: str
    severity: Severity
    risk_score: int = Field(ge=0, le=100)
    anomaly_score: float | None = None
    risk_factors: list[str] = Field(default_factory=list)
    explanation: str | None = None


class AlertCreate(AlertBase):
    pass


class AlertRead(AlertBase):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    status: AlertStatus = "new"
    detected_at: str
    updated_at: str


class AlertUpdateStatus(BaseModel):
    status: AlertStatus


class FrontendAlert(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("userId", "user_id"),
        serialization_alias="userId",
    )
    device_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("deviceId", "device_id"),
        serialization_alias="deviceId",
    )
    title: str
    severity: Severity
    status: AlertStatus
    risk_score: int = Field(
        validation_alias=AliasChoices("riskScore", "risk_score"),
        serialization_alias="riskScore",
    )
    anomaly_score: float | None = Field(
        default=None,
        validation_alias=AliasChoices("anomalyScore", "anomaly_score"),
        serialization_alias="anomalyScore",
    )
    explanation: str | None = None
    detected_at: str = Field(
        validation_alias=AliasChoices("detectedAt", "detected_at"),
        serialization_alias="detectedAt",
    )
    updated_at: str = Field(
        validation_alias=AliasChoices("updatedAt", "updated_at"),
        serialization_alias="updatedAt",
    )


class DatasetImportRequest(BaseModel):
    input_dir: str
    chunksize: int = 250000


class DatasetImportResponse(BaseModel):
    status: str
    message: str
    summary: dict[str, Any] | None = None


class FeatureBuildRequest(BaseModel):
    input_dir: str | None = None


class FeatureBuildResponse(BaseModel):
    status: str
    message: str
    feature_count: int | None = None


class ModelTrainRequest(BaseModel):
    algorithm: str = "ocsvm"
    nu: float = 0.005
    kernel: str = "rbf"
    gamma: str = "scale"


class ModelTrainResponse(BaseModel):
    status: str
    message: str
    model_version: str | None = None
    metrics: dict[str, Any] | None = None


class RawLogIngest(BaseModel):
    source_id: str
    collector_type: str
    event_type: RawLogEventType
    timestamp: str
    user_id: str | None = None
    device_id: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    ingest_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class RawLogRead(RawLogIngest):
    id: int
    normalized_event_id: int | None = None
    created_at: str


class RawLogBatchIngest(BaseModel):
    records: list[dict[str, Any]] = Field(max_length=1000)


class RawLogBatchResult(BaseModel):
    created_or_updated: int
    failed: int
    errors: list[dict[str, Any]]


class ModelInferRequest(BaseModel):
    features: dict[str, float]
    user_id: str | None = None
    device_id: str | None = None


class ModelInferResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    model_version: str = Field(serialization_alias="modelVersion")
    prediction: ModelPrediction
    is_anomaly: bool = Field(serialization_alias="isAnomaly")
    score_samples: float = Field(serialization_alias="scoreSamples")
    decision_score: float = Field(serialization_alias="decisionScore")
    anomaly_score: float = Field(serialization_alias="anomalyScore")
    risk_score: int = Field(serialization_alias="riskScore", ge=0, le=100)
    severity: Severity
    feature_columns: list[str] = Field(serialization_alias="featureColumns")
    missing_features: list[str] = Field(serialization_alias="missingFeatures")
    extra_features: list[str] = Field(serialization_alias="extraFeatures")


class ModelMetricsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    model_version: str = Field(serialization_alias="modelVersion")
    algorithm: str
    kernel: str
    gamma: str
    nu: float
    max_benign_train: int = Field(serialization_alias="maxBenignTrain")
    feature_columns: list[str] = Field(serialization_alias="featureColumns")


# ---------------------------------------------------------------------------
# Frontend-compatible response models (camelCase to match TypeScript types)
# ---------------------------------------------------------------------------


class FrontendAuthUser(BaseModel):
    id: str
    email: str
    name: str
    role: Role


class FrontendLoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(
        validation_alias=AliasChoices("accessToken", "access_token"),
        serialization_alias="accessToken",
    )
    user: FrontendAuthUser


class DashboardSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_users: int = Field(
        validation_alias=AliasChoices("totalUsers", "total_users"),
        serialization_alias="totalUsers",
    )
    total_devices: int = Field(
        validation_alias=AliasChoices("totalDevices", "total_devices"),
        serialization_alias="totalDevices",
    )
    total_logs: int = Field(
        validation_alias=AliasChoices("totalLogs", "total_logs"),
        serialization_alias="totalLogs",
    )
    open_alerts: int = Field(
        validation_alias=AliasChoices("openAlerts", "open_alerts"),
        serialization_alias="openAlerts",
    )
    high_critical_alerts: int = Field(
        validation_alias=AliasChoices("highCriticalAlerts", "high_critical_alerts"),
        serialization_alias="highCriticalAlerts",
    )
    average_risk_score: float = Field(
        validation_alias=AliasChoices("averageRiskScore", "average_risk_score"),
        serialization_alias="averageRiskScore",
    )
    current_model_version: str | None = Field(
        default=None,
        validation_alias=AliasChoices("currentModelVersion", "current_model_version"),
        serialization_alias="currentModelVersion",
    )
    last_import_time: str | None = Field(
        default=None,
        validation_alias=AliasChoices("lastImportTime", "last_import_time"),
        serialization_alias="lastImportTime",
    )


class FrontendUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    account: str
    name: str | None = None
    department: str | None = None
    role: str | None = None
    status: str
    risk_score: int | None = Field(
        default=None,
        validation_alias=AliasChoices("riskScore", "risk_score"),
        serialization_alias="riskScore",
    )
    assigned_devices: int | None = Field(
        default=None,
        validation_alias=AliasChoices("assignedDevices", "assigned_devices"),
        serialization_alias="assignedDevices",
    )
    open_alerts: int | None = Field(
        default=None,
        validation_alias=AliasChoices("openAlerts", "open_alerts"),
        serialization_alias="openAlerts",
    )
    last_seen: str | None = Field(
        default=None,
        validation_alias=AliasChoices("lastSeen", "last_seen"),
        serialization_alias="lastSeen",
    )
    devices: int | None = None
    baseline: str | None = None
    anomalies: int | None = None
    login_hours: str | None = Field(
        default=None,
        validation_alias=AliasChoices("loginHours", "login_hours"),
        serialization_alias="loginHours",
    )
    common_devices: str | None = Field(
        default=None,
        validation_alias=AliasChoices("commonDevices", "common_devices"),
        serialization_alias="commonDevices",
    )
    explanation: str | None = None


class FrontendDevice(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    hostname: str
    assigned_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices("assignedUser", "assigned_user"),
        serialization_alias="assignedUser",
    )
    department: str | None = None
    status: str
    risk_score: int | None = Field(
        default=None,
        validation_alias=AliasChoices("riskScore", "risk_score"),
        serialization_alias="riskScore",
    )
    open_alerts: int | None = Field(
        default=None,
        validation_alias=AliasChoices("openAlerts", "open_alerts"),
        serialization_alias="openAlerts",
    )
    last_seen: str | None = Field(
        default=None,
        validation_alias=AliasChoices("lastSeen", "last_seen"),
        serialization_alias="lastSeen",
    )
    owner: str | None = None
    os: str | None = None
    ip: str | None = None
    posture: str | None = None
    suspicious_events: int | None = Field(
        default=None,
        validation_alias=AliasChoices("suspiciousEvents", "suspicious_events"),
        serialization_alias="suspiciousEvents",
    )


class FrontendEventLog(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    timestamp: str
    event_type: str = Field(
        validation_alias=AliasChoices("eventType", "event_type"),
        serialization_alias="eventType",
    )
    user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("userId", "user_id"),
        serialization_alias="userId",
    )
    device_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("deviceId", "device_id"),
        serialization_alias="deviceId",
    )
    action: str
    source_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("sourceFile", "source_file"),
        serialization_alias="sourceFile",
    )
    source_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("sourceId", "source_id"),
        serialization_alias="sourceId",
    )
    raw_detail: str | None = Field(
        default=None,
        validation_alias=AliasChoices("rawDetail", "raw_detail"),
        serialization_alias="rawDetail",
    )
    user: str | None = None
    device: str | None = None
    source_ip: str | None = Field(
        default=None,
        validation_alias=AliasChoices("sourceIp", "source_ip"),
        serialization_alias="sourceIp",
    )
    resource: str | None = None
    result: str | None = None
    risk_score: int | None = Field(
        default=None,
        validation_alias=AliasChoices("riskScore", "risk_score"),
        serialization_alias="riskScore",
    )
    severity: Severity | None = None


class AnalyzeRequest(BaseModel):
    user_id: str
    events: list[dict[str, Any]]


class AnalyzeResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    risk_score: int
    top_factors: list[str]
    explanation: str


# ---------------------------------------------------------------------------
# Endpoint Agent schemas
# ---------------------------------------------------------------------------

AgentStatus = Literal["enrolled", "active", "offline", "revoked"]
BlocklistPatternType = Literal["domain", "url", "ip", "regex"]
AgentCollectorName = Literal[
    "logon", "device", "file", "http", "email", "process", "network"
]


class EnrollmentTokenCreate(BaseModel):
    expires_minutes: int = Field(default=60, ge=1, le=10080)
    note: str | None = None


class EnrollmentTokenRead(BaseModel):
    token: str
    token_id: str
    expires_at: str
    created_at: str


class AgentEnrollRequest(BaseModel):
    enrollment_token: str
    hostname: str
    os: str | None = None
    os_version: str | None = None
    device_id: str | None = None
    assigned_user_id: str | None = None


class AgentEnrollResponse(BaseModel):
    agent_id: str
    api_key: str
    policy_version: int
    issued_at: str


class AgentHeartbeatRequest(BaseModel):
    metrics: dict[str, Any] = Field(default_factory=dict)


class AgentHeartbeatResponse(BaseModel):
    status: str
    policy_version: int
    last_heartbeat: str


class AgentConfigResponse(BaseModel):
    policy_version: int
    sampling_rate: int
    enabled_collectors: list[AgentCollectorName]
    blocklist: list[dict[str, Any]]
    server_time: str


class AgentRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent_id: str
    hostname: str
    os: str | None = None
    os_version: str | None = None
    device_id: str | None = None
    assigned_user_id: str | None = None
    status: AgentStatus
    policy_version: int
    last_heartbeat: str | None = None
    last_config_pull: str | None = None
    enrolled_at: str
    created_at: str
    updated_at: str


class AgentUpdate(BaseModel):
    status: AgentStatus | None = None
    device_id: str | None = None
    assigned_user_id: str | None = None
    policy_version: int | None = Field(default=None, ge=1)


class BlocklistEntryCreate(BaseModel):
    pattern: str
    pattern_type: BlocklistPatternType = "domain"
    category: str | None = None
    reason: str | None = None
    enabled: bool = True


class BlocklistEntryUpdate(BaseModel):
    pattern: str | None = None
    pattern_type: BlocklistPatternType | None = None
    category: str | None = None
    reason: str | None = None
    enabled: bool | None = None


class BlocklistEntryRead(BaseModel):
    id: int
    pattern: str
    pattern_type: BlocklistPatternType
    category: str | None = None
    reason: str | None = None
    enabled: bool
    created_at: str
    updated_at: str


class AgentPolicyUpdate(BaseModel):
    sampling_rate: int | None = Field(default=None, ge=1, le=100)
    enabled_collectors: list[AgentCollectorName] | None = None


# ---------------------------------------------------------------------------
# LLM / chat / memory / feedback (Phase 3.6 of PLAN_LLM.md).
# ---------------------------------------------------------------------------


ChatRole = Literal["user", "assistant", "system"]
FeedbackVerdict = Literal["true_positive", "false_positive", "benign", "needs_investigation"]
MemoryScope = Literal["user", "device", "pattern", "global"]
MemoryKind = Literal["fact", "preference", "analyst_pattern", "historical"]


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    stream: bool = True
    conversation_id: int | None = None


class ChatMessageRead(BaseModel):
    id: int
    role: ChatRole
    content: str
    model: str | None = None
    latency_ms: int | None = None
    memory_used_ids: list[int] | None = None
    created_at: str


class ConversationRead(BaseModel):
    id: int
    alert_id: int
    user_id: str
    title: str
    summary: str | None = None
    messages: list[ChatMessageRead] = Field(default_factory=list)
    updated_at: str


class ConversationSummaryRead(BaseModel):
    id: int
    alert_id: int
    user_id: str
    title: str
    message_count: int = 0
    updated_at: str


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=160)


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)


class FeedbackCreate(BaseModel):
    verdict: FeedbackVerdict
    note: str | None = Field(default=None, max_length=2000)


class FeedbackRead(BaseModel):
    id: int
    alert_id: int
    analyst_id: str
    verdict: FeedbackVerdict
    note: str | None = None
    created_at: str


class MemoryRead(BaseModel):
    id: int
    scope: MemoryScope
    scope_id: str | None = None
    kind: MemoryKind
    content: str
    tags: list[str] = Field(default_factory=list)
    use_count: int
    last_used_at: str | None = None
    created_at: str
