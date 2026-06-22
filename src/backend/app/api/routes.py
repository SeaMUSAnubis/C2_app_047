from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from src.backend.app.config import settings
from src.backend.app.core.security import (
    create_access_token,
    decode_access_token,
    get_agent_from_request,
    verify_password,
)
from src.backend.app.db import session as database
from src.backend.app.schemas.schemas import (
    AccountCreate,
    AccountListItem,
    AccountPublic,
    AccountUpdate,
    AlertUpdateStatus,
    AnalyzeRequest,
    AnalyzeResponse,
    DeviceCreate,
    DeviceRead,
    DeviceUpdate,
    EventIngest,
    EventRead,
    FrontendDevice,
    FrontendEventLog,
    FrontendLoginResponse,
    FrontendUser,
    HealthResponse,
    LoginRequest,
    ModelInferRequest,
    ModelInferResponse,
    ModelMetricsResponse,
    PaginatedResponse,
    RawLogBatchIngest,
    RawLogBatchResult,
    RawLogIngest,
    RawLogRead,
    Role,
    UserCreate,
    UserRead,
    UserUpdate,
)
from src.ml.services.ueba_ml.inference import (
    ModelArtifactError,
    get_ocsvm_metrics,
    run_ocsvm_inference,
)

router = APIRouter()
security = HTTPBearer()


async def get_current_account(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict:
    payload = decode_access_token(credentials.credentials)
    account = database.get_account_by_id(int(payload["sub"]))
    if not account or not account["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")
    return account


def require_role(*roles: Role):
    async def dependency(current_account: Annotated[dict, Depends(get_current_account)]) -> dict:
        if current_account["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_account

    return dependency


async def require_role_or_agent(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))],
) -> dict:
    """Accept either a JWT bearer (human account) or X-API-Key (endpoint agent).

    Returns a dict with an `auth_kind` key ('account' or 'agent') so the caller
    can tell them apart. Used by /api/raw-logs/* so endpoint agents can ingest
    without a human login.
    """
    agent = await get_agent_from_request(request)
    if agent is not None:
        return {"auth_kind": "agent", "agent": agent}
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer, ApiKey"},
        )
    payload = decode_access_token(credentials.credentials)
    account = database.get_account_by_id(int(payload["sub"]))
    if not account or not account["is_active"]:
        raise HTTPException(status_code=401, detail="Account is inactive")
    return {"auth_kind": "account", "account": account}


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/auth/login", response_model=FrontendLoginResponse, response_model_by_alias=True)
async def login(payload: LoginRequest) -> FrontendLoginResponse:
    account = database.get_account_by_email(payload.email)
    if (
        not account
        or not account["is_active"]
        or not verify_password(payload.password, account["password_hash"])
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    token, _ = create_access_token(str(account["id"]), account["role"])
    return FrontendLoginResponse(
        access_token=token,
        user={
            "id": str(account["id"]),
            "email": account["email"],
            "name": account["full_name"],
            "role": account["role"],
        },
    )


@router.get("/auth/me", response_model=AccountPublic)
async def me(current_account: Annotated[dict, Depends(get_current_account)]) -> AccountPublic:
    return _account_public(current_account)


@router.get("/dashboard/summary")
async def dashboard_summary(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> dict[str, Any]:
    _ = current_account
    return _dashboard_summary_for_frontend()

@router.get("/dashboard/overview")
async def dashboard_overview(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> dict[str, Any]:
    _ = current_account
    return database.get_dashboard_overview()


@router.get("/users", response_model=list[FrontendUser], response_model_by_alias=True)
async def users(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=10000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    _ = current_account
    rows = database.list_frontend_users(limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(database.count_frontend_users())
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


@router.get("/users/{user_id}", response_model=UserRead)
async def user_detail(
    user_id: str, current_account: Annotated[dict, Depends(get_current_account)]
) -> dict:
    _ = current_account
    user = database.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate, current_account: Annotated[dict, Depends(require_role("admin"))]
) -> dict:
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


@router.get("/devices", response_model=list[FrontendDevice], response_model_by_alias=True)
async def devices(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=10000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    _ = current_account
    rows = database.list_frontend_devices(limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(database.count_frontend_devices())
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


@router.get("/devices/{device_id}", response_model=DeviceRead)
async def device_detail(
    device_id: str, current_account: Annotated[dict, Depends(get_current_account)]
) -> dict:
    _ = current_account
    device = database.get_device(device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post("/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate, current_account: Annotated[dict, Depends(require_role("admin"))]
) -> dict:
    _ = current_account
    if database.get_device(payload.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device already exists")
    if payload.assigned_user_id and not database.get_user(payload.assigned_user_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assigned user does not exist"
        )
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assigned user does not exist"
        )
    device = database.update_device(device_id, data)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post("/logs/ingest", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def ingest_log(
    payload: EventIngest, current_account: Annotated[dict, Depends(get_current_account)]
) -> dict:
    _ = current_account
    if payload.user_id and not database.get_user(payload.user_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="User does not exist"
        )
    if payload.device_id and not database.get_device(payload.device_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device does not exist"
        )
    return database.ingest_event(payload.model_dump())


@router.get("/logs", response_model=list[FrontendEventLog], response_model_by_alias=True)
async def logs(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=10000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    _ = current_account
    rows = database.list_frontend_logs(limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(database.count_frontend_logs())
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows

@router.get("/alerts")
async def alerts(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    _ = current_account
    rows = database.list_alerts_paged(limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(database.count_alerts(None))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [_alert_for_frontend(alert) for alert in rows]

@router.patch("/alerts/{alert_id}/status")
async def update_alert_status(
    alert_id: int,
    payload: AlertUpdateStatus,
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> dict[str, Any]:
    _ = current_account
    alert = database.update_alert_status(alert_id, payload.status)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return _alert_for_frontend(alert)


@router.post("/raw-logs/ingest", response_model=RawLogRead, status_code=status.HTTP_201_CREATED)
async def ingest_raw_log(
    payload: RawLogIngest,
    auth: Annotated[dict, Depends(require_role_or_agent)],
) -> dict:
    if auth["auth_kind"] == "agent":
        agent = auth["agent"]
        if not payload.user_id and agent.get("assigned_user_id"):
            payload = payload.model_copy(update={"user_id": agent["assigned_user_id"]})
        if not payload.device_id and agent.get("device_id"):
            payload = payload.model_copy(update={"device_id": agent["device_id"]})
    else:
        account = auth["account"]
        if account["role"] not in ("admin", "security_manager", "analyst"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    return database.ingest_raw_log(payload.model_dump())


@router.post("/raw-logs/batch", response_model=RawLogBatchResult)
async def batch_ingest_raw_logs(
    payload: RawLogBatchIngest,
    auth: Annotated[dict, Depends(require_role_or_agent)],
) -> dict:
    if auth["auth_kind"] == "account":
        account = auth["account"]
        if account["role"] not in ("admin", "security_manager", "analyst"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    agent = auth.get("agent") if auth["auth_kind"] == "agent" else None
    default_user_id = agent.get("assigned_user_id") if agent else None
    default_device_id = agent.get("device_id") if agent else None
    valid_records: list[dict[str, Any]] = []
    failed = 0
    errors: list[dict[str, Any]] = []
    for idx, record in enumerate(payload.records):
        try:
            validated = RawLogIngest.model_validate(record)
            if not validated.user_id and default_user_id:
                validated = validated.model_copy(update={"user_id": default_user_id})
            if not validated.device_id and default_device_id:
                validated = validated.model_copy(update={"device_id": default_device_id})
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
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
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
    return _paginated(
        database.list_raw_logs(filters), database.count_raw_logs(filters), limit, offset
    )


@router.get("/raw-logs/{log_id}", response_model=RawLogRead)
async def raw_log_detail(
    log_id: int,
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> dict:
    _ = current_account
    log = database.get_raw_log(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw log not found")
    return log


@router.post(
    "/models/{model_version}/infer",
    response_model=ModelInferResponse,
    response_model_by_alias=True,
)
async def infer_model(
    model_version: str,
    payload: ModelInferRequest,
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> ModelInferResponse:
    _ = current_account
    if model_version != settings.ocsvm_model_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    try:
        return run_ocsvm_inference(payload.features)
    except ModelArtifactError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get(
    "/models/{model_version}",
    response_model=ModelMetricsResponse,
    response_model_by_alias=True,
)
async def model_detail(
    model_version: str,
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> ModelMetricsResponse:
    _ = current_account
    return _model_metrics_response(model_version)


@router.get(
    "/models/{model_version}/metrics",
    response_model=ModelMetricsResponse,
    response_model_by_alias=True,
)
async def model_metrics(
    model_version: str,
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> ModelMetricsResponse:
    _ = current_account
    return _model_metrics_response(model_version)


def _model_metrics_response(model_version: str) -> ModelMetricsResponse:
    if model_version != settings.ocsvm_model_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    try:
        return get_ocsvm_metrics()
    except ModelArtifactError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _account_public(account: dict) -> AccountPublic:
    return AccountPublic(
        id=account["id"],
        email=account["email"],
        full_name=account["full_name"],
        role=account["role"],
    )


def _paginated(items: list[dict], total: int, limit: int, offset: int) -> PaginatedResponse:
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


def _dashboard_summary_for_frontend() -> dict[str, Any]:
    summary = database.get_dashboard_summary()
    total_users = int(summary.get("totalUsers", 0))
    open_alerts = int(summary.get("openAlerts", 0))
    high_critical_alerts = int(summary.get("highCriticalAlerts", 0))
    return {
        **summary,
        "total_users": total_users,
        "total_devices": int(summary.get("totalDevices", 0)),
        "total_logs": int(summary.get("totalLogs", 0)),
        "active_alerts": open_alerts,
        "open_alerts": open_alerts,
        "high_risk_users": high_critical_alerts,
        "critical_alerts": high_critical_alerts,
        "blocked_websites": 0,
        "average_risk_score": summary.get("averageRiskScore", 0),
        "current_model_version": summary.get("currentModelVersion"),
        "last_import_time": summary.get("lastImportTime"),
    }


def _alert_for_frontend(alert: dict[str, Any]) -> dict[str, Any]:
    risk_factors = alert.get("risk_factors") or []
    risk_score = int(alert.get("risk_score", 0) or 0)
    detected_at = alert.get("detected_at")
    user_name = alert.get("user_name") or alert.get("user_id")
    device_name = alert.get("device_name") or alert.get("device_id")
    user_id = alert.get("user_id")
    device_id = alert.get("device_id")
    return {
        "id": str(alert.get("id")),
        "numeric_id": alert.get("id"),
        "numericId": alert.get("id"),
        "user_id": user_id,
        "userId": user_id,
        "user_name": user_name,
        "userName": user_name,
        "user": user_name,
        "device_id": device_id,
        "deviceId": device_id,
        "device_name": device_name,
        "deviceName": device_name,
        "device": device_name,
        "risk_score": risk_score,
        "riskScore": risk_score,
        "severity": alert.get("severity", "medium"),
        "status": alert.get("status", "new"),
        "main_reason": alert.get("title", "Suspicious behavior detected"),
        "title": alert.get("title", "Suspicious behavior detected"),
        "created_at": detected_at,
        "time": detected_at,
        "timestamp": detected_at,
        "updated_at": alert.get("updated_at"),
        "model_version": alert.get("model_version"),
        "top_anomalous_features": risk_factors,
        "evidence": risk_factors or ["Risk score vượt ngưỡng", "Hành vi lệch baseline"],
        "action": "Triage alert, xác minh tài khoản và kiểm tra endpoint.",
        "mitre": "UEBA - Behavioral Anomaly",
        "explanation": alert.get("explanation"),
        "suspicious_urls": [],
    }


@router.post("/demo/analyze", response_model=AnalyzeResponse)
@router.post("/analysis/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager", "analyst"))],
) -> dict:
    _ = current_account
    from src.backend.app.db.session import list_events
    from src.backend.app.services.demo_pipeline import demo_pipeline

    events = payload.events
    if not events and payload.user_id:
        from src.backend.app.services.demo_pipeline import load_user_events_from_demo_csv
        csv_events = load_user_events_from_demo_csv(payload.user_id)
        if csv_events:
            events = csv_events
        else:
            db_events = list_events({"user_id": payload.user_id})
            events = db_events

    print(f"\n[Analysis] Bắt đầu phân tích cho user: {payload.user_id}")
    print(f"[Analysis] Đang xử lý {len(events)} sự kiện qua model One-Class SVM...")
    
    result = demo_pipeline.analyze(events, payload.user_id)
    
    if "error" in result:
        print(f"[Analysis] Lỗi: {result['error']}")
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "risk_score": 0,
            "top_factors": [],
            "explanation": result["error"],
        }
        
    print("[Analysis] Phân tích hoàn tất!")
    print(f"[Analysis] - Bất thường (Anomaly): {result.get('is_anomaly')}")
    print(f"[Analysis] - Điểm rủi ro (Risk Score): {result.get('risk_score')}")
        
    if result.get("is_anomaly"):
        from src.backend.app.db.session import create_alert
        top_factors = result.get("top_factors", [])
        risk_score = result.get("risk_score", 0)
        
        if top_factors:
            title = f"Suspicious Behavior: {', '.join(top_factors)}"
        else:
            title = "Suspicious Behavior Detected"
            
        alert_payload = {
            "user_id": payload.user_id,
            "title": title,
            "risk_score": risk_score,
            "anomaly_score": result.get("anomaly_score"),
            "risk_factors": top_factors,
            "explanation": result.get("explanation"),
            "severity": "high" if risk_score > 70 else "medium",
            "status": "new"
        }
        try:
            create_alert(alert_payload)
        except Exception as e:
            print(f"Failed to create alert: {e}")

    return result

@router.post("/demo/analyze-all")
@router.post("/analysis/analyze-all")
async def analyze_all(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager"))],
) -> dict:
    _ = current_account
    from src.backend.app.db.session import create_alert, list_events, list_users
    from src.backend.app.services.demo_pipeline import demo_pipeline
    
    print("\n[Analysis All] Bắt đầu phân tích toàn bộ user...")
    users = list_users({})
    total_users = len(users)
    anomalies_found = 0
    errors = 0
    
    print(f"[Analysis All] Tìm thấy {total_users} users. Bắt đầu phân tích từng user...")
    
    for _i, user in enumerate(users):
        user_id = user["id"]
        # print(f"[{i+1}/{total_users}] Analyzing user {user_id}...")
        events = list_events({"user_id": user_id})
        
        if not events:
            continue
            
        result = demo_pipeline.analyze(events, user_id)
        if "error" in result:
            errors += 1
            continue
            
        if result.get("is_anomaly"):
            anomalies_found += 1
            top_factors = result.get("top_factors", [])
            risk_score = result.get("risk_score", 0)
            
            if top_factors:
                title = f"Suspicious Behavior: {', '.join(top_factors)}"
            else:
                title = "Suspicious Behavior Detected"
                
            alert_payload = {
                "user_id": user_id,
                "title": title,
                "risk_score": risk_score,
                "anomaly_score": result.get("anomaly_score"),
                "risk_factors": top_factors,
                "explanation": result.get("explanation"),
                "severity": "high" if risk_score > 70 else "medium",
                "status": "new"
            }
            try:
                create_alert(alert_payload)
            except Exception as e:
                print(f"Failed to create alert for {user_id}: {e}")
                
    print(f"[Analysis All] Hoàn tất! Phân tích {total_users} users. Phát hiện {anomalies_found} bất thường.")
    
    return {
        "status": "completed",
        "total_users_analyzed": total_users,
        "anomalies_found": anomalies_found,
        "errors": errors
    }

@router.post("/datasets/cert-r42/import")
async def import_demo_data(
    current_account: Annotated[dict, Depends(require_role("admin", "security_manager"))],
) -> dict:
    _ = current_account
    try:
        from src.database.load_demo_data import main as seed_main
        stats = seed_main()
        return {
            "job_id": "import_demo_001",
            "status": "completed",
            "summary": stats
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/me/overview")
async def me_overview(
    current_account: Annotated[dict, Depends(get_current_account)],
) -> dict[str, Any]:
    overview = database.get_employee_overview(int(current_account["id"]))
    if not overview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản chưa được liên kết với người dùng nào",
        )
    return overview


@router.get("/admin/accounts", response_model=list[AccountListItem])
async def admin_list_accounts(
    current_account: Annotated[dict, Depends(require_role("admin"))],
) -> list[dict[str, Any]]:
    _ = current_account
    return database.list_accounts()


@router.post("/admin/accounts", response_model=AccountListItem, status_code=status.HTTP_201_CREATED)
async def admin_create_account(
    payload: AccountCreate,
    current_account: Annotated[dict, Depends(require_role("admin"))],
) -> dict[str, Any]:
    _ = current_account
    existing = database.get_account_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại")
    return database.create_account(payload.model_dump())


@router.patch("/admin/accounts/{account_id}", response_model=AccountListItem)
async def admin_update_account(
    account_id: int,
    payload: AccountUpdate,
    current_account: Annotated[dict, Depends(require_role("admin"))],
) -> dict[str, Any]:
    _ = current_account
    if account_id == int(current_account["id"]) and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể khóa tài khoản đang đăng nhập",
        )
    account = database.update_account(account_id, payload.model_dump(exclude_unset=True))
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tài khoản không tồn tại")
    return account
