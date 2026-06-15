from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from src.models.schemas import (
    AccountPublic,
    DeviceCreate,
    DeviceRead,
    DeviceStatus,
    DeviceUpdate,
    EventIngest,
    EventRead,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    PaginatedResponse,
    RawLogBatchIngest,
    RawLogBatchResult,
    RawLogIngest,
    RawLogRead,
    Role,
    UserCreate,
    UserRead,
    UserStatus,
    UserUpdate,
)
from src.services import database
from src.services.auth import create_access_token, decode_access_token, verify_password

router = APIRouter()
security = HTTPBearer()


async def get_current_account(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> dict:
    payload = decode_access_token(credentials.credentials)
    account = database.get_account_by_id(int(payload["sub"]))
    if not account or not account["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")
    return account


def require_role(*roles: Role):
    async def dependency(current_account: Annotated[dict, Depends(get_current_account)]) -> dict:
        if current_account["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_account

    return dependency


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    account = database.get_account_by_email(payload.email)
    if not account or not account["is_active"] or not verify_password(payload.password, account["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token, expires_in = create_access_token(str(account["id"]), account["role"])
    return LoginResponse(access_token=token, expires_in=expires_in, user=_account_public(account))


@router.get("/auth/me", response_model=AccountPublic)
async def me(current_account: Annotated[dict, Depends(get_current_account)]) -> AccountPublic:
    return _account_public(current_account)


@router.get("/users", response_model=PaginatedResponse)
async def users(
    current_account: Annotated[dict, Depends(get_current_account)],
    department: str | None = None,
    job_role: str | None = None,
    status_filter: Annotated[UserStatus | None, Query(alias="status")] = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse:
    _ = current_account
    filters = {
        "department": department,
        "job_role": job_role,
        "status": status_filter,
        "search": search,
        "limit": limit,
        "offset": offset,
    }
    return _paginated(database.list_users(filters), database.count_users(filters), limit, offset)


@router.get("/users/{user_id}", response_model=UserRead)
async def user_detail(user_id: str, current_account: Annotated[dict, Depends(get_current_account)]) -> dict:
    _ = current_account
    user = database.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, current_account: Annotated[dict, Depends(require_role("admin"))]) -> dict:
    _ = current_account
    if database.get_user(payload.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    return database.create_user(payload.model_dump())


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    current_account: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    _ = current_account
    user = database.update_user(user_id, payload.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/devices", response_model=PaginatedResponse)
async def devices(
    current_account: Annotated[dict, Depends(get_current_account)],
    status_filter: Annotated[DeviceStatus | None, Query(alias="status")] = None,
    os: str | None = None,
    assigned_user_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse:
    _ = current_account
    filters = {
        "status": status_filter,
        "os": os,
        "assigned_user_id": assigned_user_id,
        "limit": limit,
        "offset": offset,
    }
    return _paginated(database.list_devices(filters), database.count_devices(filters), limit, offset)


@router.get("/devices/{device_id}", response_model=DeviceRead)
async def device_detail(device_id: str, current_account: Annotated[dict, Depends(get_current_account)]) -> dict:
    _ = current_account
    device = database.get_device(device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post("/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device(payload: DeviceCreate, current_account: Annotated[dict, Depends(require_role("admin"))]) -> dict:
    _ = current_account
    if database.get_device(payload.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device already exists")
    if payload.assigned_user_id and not database.get_user(payload.assigned_user_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assigned user does not exist")
    return database.create_device(payload.model_dump())


@router.patch("/devices/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: str,
    payload: DeviceUpdate,
    current_account: Annotated[dict, Depends(require_role("admin"))],
) -> dict:
    _ = current_account
    data = payload.model_dump(exclude_unset=True)
    assigned_user_id = data.get("assigned_user_id")
    if assigned_user_id and not database.get_user(assigned_user_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assigned user does not exist")
    device = database.update_device(device_id, data)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post("/logs/ingest", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def ingest_log(payload: EventIngest, current_account: Annotated[dict, Depends(get_current_account)]) -> dict:
    _ = current_account
    if payload.user_id and not database.get_user(payload.user_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="User does not exist")
    if payload.device_id and not database.get_device(payload.device_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device does not exist")
    return database.ingest_event(payload.model_dump())


@router.get("/logs", response_model=PaginatedResponse)
async def logs(
    current_account: Annotated[dict, Depends(get_current_account)],
    user_id: str | None = None,
    device_id: str | None = None,
    event_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse:
    _ = current_account
    filters = {
        "user_id": user_id,
        "device_id": device_id,
        "event_type": event_type,
        "limit": limit,
        "offset": offset,
    }
    return _paginated(database.list_events(filters), database.count_events(filters), limit, offset)


@router.post("/raw-logs/ingest", response_model=RawLogRead, status_code=status.HTTP_201_CREATED)
async def ingest_raw_log(
    payload: RawLogIngest,
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
) -> dict:
    _ = current_account
    return database.ingest_raw_log(payload.model_dump())


@router.post("/raw-logs/batch", response_model=RawLogBatchResult)
async def batch_ingest_raw_logs(
    payload: RawLogBatchIngest,
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
) -> dict:
    _ = current_account
    valid_records: list[dict[str, Any]] = []
    failed = 0
    errors: list[dict[str, Any]] = []
    for idx, record in enumerate(payload.records):
        try:
            validated = RawLogIngest.model_validate(record)
            valid_records.append(validated.model_dump())
        except ValidationError as exc:
            failed += 1
            errors.append({"index": idx, "error": exc.errors()[0]["msg"]})
    if valid_records:
        result = database.batch_ingest_raw_logs(valid_records)
        created_or_updated = result["created_or_updated"]
        failed += result["failed"]
        errors.extend(result["errors"])
    else:
        created_or_updated = 0
    return {"created_or_updated": created_or_updated, "failed": failed, "errors": errors}


@router.get("/raw-logs", response_model=PaginatedResponse)
async def raw_logs(
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
    user_id: str | None = None,
    device_id: str | None = None,
    event_type: str | None = None,
    collector_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse:
    _ = current_account
    filters = {
        "user_id": user_id,
        "device_id": device_id,
        "event_type": event_type,
        "collector_type": collector_type,
        "limit": limit,
        "offset": offset,
    }
    return _paginated(database.list_raw_logs(filters), database.count_raw_logs(filters), limit, offset)


@router.get("/raw-logs/{log_id}", response_model=RawLogRead)
async def raw_log_detail(
    log_id: int,
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
) -> dict:
    _ = current_account
    log = database.get_raw_log(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw log not found")
    return log


def _account_public(account: dict) -> AccountPublic:
    return AccountPublic(
        id=account["id"],
        email=account["email"],
        full_name=account["full_name"],
        role=account["role"],
    )


def _paginated(items: list[dict], total: int, limit: int, offset: int) -> PaginatedResponse:
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
