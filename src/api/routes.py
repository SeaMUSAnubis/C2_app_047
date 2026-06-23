from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from src.config import settings
from src.models.explanation import (
    AlertExplanationRequest,
    AlertExplanationResponse,
    AnomalyFeatureInput,
)
from src.models.schemas import (
    AccountPublic,
    AnalyzeRequest,
    AnalyzeResponse,
    DashboardSummary,
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
from src.services import database
from src.services.auth import create_access_token, decode_access_token, verify_password
from src.services.llm.explanation_service import generate_explanation
from src.services.ueba_ml.inference import (
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


@router.get("/dashboard/summary", response_model=DashboardSummary, response_model_by_alias=True)
async def dashboard_summary(
    current_account: Annotated[dict, Depends(get_current_account)],
) -> dict[str, Any]:
    _ = current_account
    return database.get_dashboard_summary()


@router.get("/users", response_model=list[FrontendUser], response_model_by_alias=True)
async def users(
    current_account: Annotated[dict, Depends(get_current_account)],
) -> list[dict[str, Any]]:
    _ = current_account
    return database.list_frontend_users()


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
    current_account: Annotated[dict, Depends(get_current_account)],
) -> list[dict[str, Any]]:
    _ = current_account
    return database.list_frontend_devices()


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
    current_account: Annotated[dict, Depends(get_current_account)],
) -> list[dict[str, Any]]:
    _ = current_account
    return database.list_frontend_logs()


@router.get("/alerts")
async def alerts(
    current_account: Annotated[dict, Depends(get_current_account)],
) -> list[dict[str, Any]]:
    _ = current_account
    return database.list_frontend_alerts()


@router.get("/alerts/{alert_id}/explanation", response_model=AlertExplanationResponse)
async def get_alert_explanation(
    alert_id: int,
    current_account: Annotated[dict, Depends(get_current_account)],
) -> AlertExplanationResponse:
    from src.services.llm.explanation_service import compute_evidence_hash
    _ = current_account
    alert = database.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
            
    features = []
    if alert.get("risk_factors"):
        for factor in alert["risk_factors"]:
            features.append(AnomalyFeatureInput(feature_name=str(factor)))
            
    req = AlertExplanationRequest(
        alert_id=str(alert["id"]),
        user_id=str(alert["user_id"] or ""),
        device_id=str(alert.get("device_id") or ""),
        risk_score=float(alert["risk_score"]),
        severity=alert["severity"],
        alert_status=alert["status"],
        anomaly_score=alert.get("anomaly_score"),
        main_reason=alert["title"],
        anomalous_features=features,
    )
    
    current_hash = compute_evidence_hash(req)
    
    if alert.get("explanation"):
        try:
            import json
            exp_data = json.loads(alert["explanation"])
            cached_response = AlertExplanationResponse.model_validate(exp_data)
            if cached_response.evidence_hash == current_hash:
                return cached_response
        except Exception:
            pass
    
    explanation = generate_explanation(req)
    database.update_alert_explanation(alert_id, explanation.model_dump_json(exclude_unset=True))
    return explanation


@router.post("/alerts/{alert_id}/explanation/regenerate", response_model=AlertExplanationResponse)
async def regenerate_alert_explanation(
    alert_id: int,
    current_account: Annotated[dict, Depends(require_role("admin"))],
) -> AlertExplanationResponse:
    _ = current_account
    alert = database.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    features = []
    if alert.get("risk_factors"):
        for factor in alert["risk_factors"]:
            features.append(AnomalyFeatureInput(feature_name=str(factor)))
            
    req = AlertExplanationRequest(
        alert_id=str(alert["id"]),
        user_id=str(alert["user_id"] or ""),
        device_id=str(alert.get("device_id") or ""),
        risk_score=float(alert["risk_score"]),
        severity=alert["severity"],
        alert_status=alert["status"],
        anomaly_score=alert.get("anomaly_score"),
        main_reason=alert["title"],
        anomalous_features=features,
    )
    
    explanation = generate_explanation(req)
    database.update_alert_explanation(alert_id, explanation.model_dump_json(exclude_unset=True))
    return explanation


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
    return _paginated(
        database.list_raw_logs(filters), database.count_raw_logs(filters), limit, offset
    )


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


@router.post(
    "/models/{model_version}/infer",
    response_model=ModelInferResponse,
    response_model_by_alias=True,
)
async def infer_model(
    model_version: str,
    payload: ModelInferRequest,
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
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
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
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
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
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


@router.post("/analysis/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
) -> dict:
    from src.services.database import list_events
    from src.services.demo_pipeline import demo_pipeline

    events = payload.events
    if not events and payload.user_id:
        from src.services.demo_pipeline import load_user_events_from_demo_csv
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
        
    print("[Analysis] Phân tích hoàn tất!")
    print(f"[Analysis] - Bất thường (Anomaly): {result.get('is_anomaly')}")
    print(f"[Analysis] - Điểm rủi ro (Risk Score): {result.get('risk_score')}")
        
    if result.get("is_anomaly"):
        from src.services.database import create_alert
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
            # Prevent crashing if DB insert fails
            print(f"Failed to create alert: {e}")

    return result

@router.post("/analysis/analyze-all")
async def analyze_all() -> dict:
    from src.services.database import create_alert, list_events, list_users
    from src.services.demo_pipeline import demo_pipeline
    
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
    current_account: Annotated[dict, Depends(require_role("admin", "analyst"))],
) -> dict:
    _ = current_account
    try:
        from src.scripts.seed_mock_data import main as seed_main
        stats = seed_main()
        return {
            "job_id": "import_demo_001",
            "status": "completed",
            "summary": stats
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

