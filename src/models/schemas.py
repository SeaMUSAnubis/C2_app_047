from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: str


Role = Literal["admin", "analyst"]
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
    "logon", "device", "file", "http", "email", "process", "network", "ldap", "psychometric", "custom"
]


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
