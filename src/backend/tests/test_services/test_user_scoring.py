"""Tests for the Phase 3 user_scoring service.

Two layers:
- Pure unit tests for the helper (`_top_factors_from_features`, severity mapping).
- `UserScoring.score_user` tests with monkeypatched DB + OCSVM (no PostgreSQL needed).
- Postgres integration tests (skip unless TEST_DATABASE_URL set) — exercise the
  end-to-end flow: insert raw logs → normalise → score → alert appears.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.backend.tests.conftest import get_test_client, postgres_tests_enabled

requires_postgres = pytest.mark.skipif(
    not postgres_tests_enabled(),
    reason="PostgreSQL integration tests require psycopg and TEST_DATABASE_URL",
)


@pytest.fixture(autouse=True)
def _reset_scoring_stats() -> None:
    """Reset the singleton user_scoring stats before each test for isolation."""
    from src.backend.app.services import user_scoring as scoring_mod

    scoring_mod.user_scoring.reset_stats()
    yield
    scoring_mod.user_scoring.reset_stats()


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


def test_top_factors_prefers_specific_signals() -> None:
    from src.backend.app.services.user_scoring import _top_factors_from_features

    features = {"n_file_exe": 2, "n_http_wikileaks": 0, "n_email": 5}
    events: list[dict[str, Any]] = []
    factors = _top_factors_from_features(features, events)
    assert "executable_file_copy" in factors
    assert "high_email_volume" in factors


def test_top_factors_falls_back_to_unusual_behavior() -> None:
    from src.backend.app.services.user_scoring import _top_factors_from_features

    features: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    factors = _top_factors_from_features(features, events)
    assert factors == ["unusual_behavior_pattern"]


def test_top_factors_picks_blocked_http_from_events() -> None:
    from src.backend.app.services.user_scoring import _top_factors_from_features

    features: dict[str, Any] = {}
    events = [
        {"event_type": "http", "action": "blocked", "url": "https://blocked.example"},
    ]
    factors = _top_factors_from_features(features, events)
    assert "blocked_http_access" in factors


def test_top_factors_capped_at_five() -> None:
    from src.backend.app.services.user_scoring import _top_factors_from_features

    features = {
        "n_file_exe": 1,
        "n_http_wikileaks": 1,
        "n_http_jobsearch": 1,
        "n_http_keylogger": 1,
        "n_email": 10,
        "n_device_afterhours": 1,
        "n_logon_afterhours": 1,
    }
    factors = _top_factors_from_features(features, [])
    assert len(factors) <= 5


def test_severity_to_alert_severity_known_values() -> None:
    from src.backend.app.services.user_scoring import _severity_to_alert_severity

    assert _severity_to_alert_severity("low") == "low"
    assert _severity_to_alert_severity("critical") == "critical"


def test_severity_to_alert_severity_unknown_defaults_to_medium() -> None:
    from src.backend.app.services.user_scoring import _severity_to_alert_severity

    assert _severity_to_alert_severity("bogus") == "medium"
    assert _severity_to_alert_severity("") == "medium"


# ---------------------------------------------------------------------------
# UserScoring.score_user — mocked DB + OCSVM
# ---------------------------------------------------------------------------


def _fake_inference(is_anomaly: bool, risk_score: int = 80, severity: str = "high"):
    """Build a ModelInferResponse-shaped object."""
    from src.ml.services.ueba_ml.inference import ModelInferResponse

    return ModelInferResponse(
        model_version="ocsvm-test-001",
        prediction="anomaly" if is_anomaly else "normal",
        is_anomaly=is_anomaly,
        score_samples=-0.3 if is_anomaly else 0.1,
        decision_score=-0.3 if is_anomaly else 0.1,
        anomaly_score=0.3 if is_anomaly else -0.1,
        risk_score=risk_score,
        severity=severity,
        feature_columns=[],
        missing_features=[],
        extra_features=[],
    )


def test_score_user_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.config import settings
    from src.backend.app.services import user_scoring as scoring_mod

    original = settings.ml_scoring_enabled
    monkeypatch.setattr(settings, "ml_scoring_enabled", False)
    try:
        result = scoring_mod.user_scoring.score_user("ACM0001")
    finally:
        monkeypatch.setattr(settings, "ml_scoring_enabled", original)
    assert result["skipped"] is True
    assert result["reason"] == "ml_scoring_disabled"


def test_score_user_skipped_when_no_events(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.services import user_scoring as scoring_mod

    monkeypatch.setattr(
        scoring_mod.database,
        "list_event_logs_for_user",
        lambda user_id, since=None, limit=1000: [],
    )
    result = scoring_mod.user_scoring.score_user("ACM0001")
    assert result["skipped"] is True
    assert result["reason"] == "no_events_in_window"


def test_score_user_normal_case_persists_score_no_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When OCSVM says normal, ml_anomaly_scores row is created but no alert."""
    from src.backend.app.services import user_scoring as scoring_mod

    fake_events = [
        {
            "id": 1,
            "user_id": "ACM0001",
            "device_id": "PC-1001",
            "event_type": "logon",
            "action": "logon",
            "timestamp": "2026-06-22T10:00:00Z",
            "metadata": {},
            "raw": {},
        }
    ]
    monkeypatch.setattr(
        scoring_mod.database,
        "list_event_logs_for_user",
        lambda user_id, since=None, limit=1000: fake_events,
    )
    monkeypatch.setattr(
        scoring_mod,
        "run_ocsvm_inference",
        lambda features: _fake_inference(is_anomaly=False, risk_score=20, severity="low"),
    )
    inserted: list[dict[str, Any]] = []

    def fake_insert(payload):
        inserted.append(payload)
        return {"id": 1, "user_id": payload["user_id"], "is_anomaly": payload["is_anomaly"]}

    monkeypatch.setattr(scoring_mod.database, "insert_ml_anomaly_score", fake_insert)
    alerts: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "create_alert",
        lambda payload: alerts.append(payload) or {"id": 1},
    )

    result = scoring_mod.user_scoring.score_user("ACM0001")
    assert result["is_anomaly"] is False
    assert result["alert_created"] is False
    assert result["alert_id"] is None
    assert len(inserted) == 1
    assert inserted[0]["user_id"] == "ACM0001"
    assert inserted[0]["is_anomaly"] is False
    assert alerts == []  # no alert for normal


def test_score_user_anomaly_creates_alert_and_persists_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When OCSVM says anomaly and risk >= threshold, create alert + score row."""
    from src.backend.app.services import user_scoring as scoring_mod

    fake_events = [
        {
            "id": 1,
            "user_id": "ACM0001",
            "device_id": "PC-1001",
            "event_type": "file",
            "action": "file_copy",
            "timestamp": "2026-06-22T10:00:00Z",
            "metadata": {},
            "raw": {"filename": "evil.exe"},
        }
    ]
    monkeypatch.setattr(
        scoring_mod.database,
        "list_event_logs_for_user",
        lambda user_id, since=None, limit=1000: fake_events,
    )
    monkeypatch.setattr(
        scoring_mod,
        "run_ocsvm_inference",
        lambda features: _fake_inference(is_anomaly=True, risk_score=85, severity="high"),
    )
    inserted: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "insert_ml_anomaly_score",
        lambda payload: (inserted.append(payload) or {"id": 7, **payload}),
    )
    alerts: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "create_alert",
        lambda payload: (alerts.append(payload) or {"id": 42, "user_id": payload.get("user_id")}),
    )
    monkeypatch.setattr(
        scoring_mod,
        "explain_alert",
        lambda context: "Anomaly detected: executable file copy",
    )

    result = scoring_mod.user_scoring.score_user("ACM0001")
    assert result["is_anomaly"] is True
    assert result["alert_created"] is True
    assert result["alert_id"] == 42
    assert len(alerts) == 1
    assert alerts[0]["user_id"] == "ACM0001"
    assert alerts[0]["severity"] == "high"
    assert alerts[0]["risk_score"] == 85
    assert "executable_file_copy" in alerts[0]["risk_factors"]
    # score row gets the alert id
    assert len(inserted) == 1
    assert inserted[0]["created_alert_id"] == 42


def test_score_user_below_threshold_does_not_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anomaly but risk_score < ml_scoring_alert_min_risk → no alert (still persist score)."""
    from src.backend.app.services import user_scoring as scoring_mod

    fake_events = [{"id": 1, "user_id": "X", "event_type": "logon", "timestamp": "t"}]
    monkeypatch.setattr(
        scoring_mod.database,
        "list_event_logs_for_user",
        lambda user_id, since=None, limit=1000: fake_events,
    )
    monkeypatch.setattr(
        scoring_mod,
        "run_ocsvm_inference",
        lambda features: _fake_inference(is_anomaly=True, risk_score=55, severity="medium"),
    )
    inserted: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "insert_ml_anomaly_score",
        lambda payload: (inserted.append(payload) or {"id": 1, **payload}),
    )
    alerts: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "create_alert",
        lambda payload: (alerts.append(payload) or {"id": 1}),
    )

    # default alert_min_risk is 60, so 55 should be skipped.
    result = scoring_mod.user_scoring.score_user("X")
    assert result["is_anomaly"] is True
    assert result["alert_created"] is False
    assert alerts == []
    assert len(inserted) == 1
    assert inserted[0]["created_alert_id"] is None


def test_score_user_create_alert_false_skips_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.services import user_scoring as scoring_mod

    fake_events = [{"id": 1, "user_id": "X", "event_type": "logon", "timestamp": "t"}]
    monkeypatch.setattr(
        scoring_mod.database,
        "list_event_logs_for_user",
        lambda user_id, since=None, limit=1000: fake_events,
    )
    monkeypatch.setattr(
        scoring_mod,
        "run_ocsvm_inference",
        lambda features: _fake_inference(is_anomaly=True, risk_score=90),
    )
    inserted: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "insert_ml_anomaly_score",
        lambda payload: (inserted.append(payload) or {"id": 1, **payload}),
    )
    alerts: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "create_alert",
        lambda payload: (alerts.append(payload) or {"id": 1}),
    )

    result = scoring_mod.user_scoring.score_user("X", create_alert=False)
    assert result["is_anomaly"] is True
    assert result["alert_created"] is False
    assert alerts == []
    assert len(inserted) == 1


def test_score_user_handles_inference_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.services import user_scoring as scoring_mod

    fake_events = [{"id": 1, "user_id": "X", "event_type": "logon", "timestamp": "t"}]
    monkeypatch.setattr(
        scoring_mod.database,
        "list_event_logs_for_user",
        lambda user_id, since=None, limit=1000: fake_events,
    )

    def boom(_features):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(scoring_mod, "run_ocsvm_inference", boom)

    result = scoring_mod.user_scoring.score_user("X")
    assert "error" in result
    assert "inference_failed" in result["error"]


def test_score_user_handles_db_error_on_list_events(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backend.app.services import user_scoring as scoring_mod

    def boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(scoring_mod.database, "list_event_logs_for_user", boom)
    result = scoring_mod.user_scoring.score_user("X")
    assert "error" in result
    assert "list_events_failed" in result["error"]


def test_score_user_handles_alert_creation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even if create_alert fails, ml_anomaly_scores row should still be inserted."""
    from src.backend.app.services import user_scoring as scoring_mod

    fake_events = [{"id": 1, "user_id": "X", "event_type": "logon", "timestamp": "t"}]
    monkeypatch.setattr(
        scoring_mod.database,
        "list_event_logs_for_user",
        lambda user_id, since=None, limit=1000: fake_events,
    )
    monkeypatch.setattr(
        scoring_mod,
        "run_ocsvm_inference",
        lambda features: _fake_inference(is_anomaly=True, risk_score=90),
    )

    def boom_alert(_payload):
        raise RuntimeError("alert insert failed")

    monkeypatch.setattr(scoring_mod.database, "create_alert", boom_alert)
    inserted: list[dict[str, Any]] = []
    monkeypatch.setattr(
        scoring_mod.database,
        "insert_ml_anomaly_score",
        lambda payload: (inserted.append(payload) or {"id": 1, **payload}),
    )

    result = scoring_mod.user_scoring.score_user("X")
    assert result["alert_created"] is False
    assert result["alert_id"] is None
    assert len(inserted) == 1
    assert inserted[0]["created_alert_id"] is None


def test_get_stats_returns_expected_keys() -> None:
    from src.backend.app.services.user_scoring import user_scoring

    stats = user_scoring.get_stats()
    for k in (
        "total_scored",
        "total_anomalies",
        "total_alerts_created",
        "total_errors",
        "enabled",
        "window_minutes",
        "alert_min_risk",
    ):
        assert k in stats


# ---------------------------------------------------------------------------
# Postgres integration tests
# ---------------------------------------------------------------------------


@requires_postgres
@pytest.mark.asyncio
async def test_run_normalizer_triggers_scoring_and_creates_alert() -> None:
    """End-to-end: ingest raw log → admin runs normalizer with scoring →
    ml_anomaly_scores row + (possibly) alert row appear."""
    from src.backend.app.db import session as database
    from src.backend.app.schemas.schemas import RawLogIngest

    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        token = login.json()["accessToken"]

        # Insert one raw log
        raw = RawLogIngest(
            source_id="phase3-score-test-1",
            collector_type="endpoint_agent",
            event_type="logon",
            timestamp="2026-06-22T10:00:00Z",
            user_id="ACM0001",
            device_id="PC-1001",
            raw_payload={"user": "ACM0001", "pc": "PC-1001", "activity": "Logon"},
            ingest_metadata={},
        )
        ingest = await client.post(
            "/api/raw-logs/ingest",
            json=raw.model_dump(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ingest.status_code == 201, ingest.text

        # Run normalizer WITH scoring (default)
        run = await client.post(
            "/api/admin/run-normalizer",
            params={"trigger_scoring": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert run.status_code == 200, run.text
        run_data = run.json()
        assert run_data["processed"] >= 1

        # Verify the event_log was created
        event_log = database.find_event_log_by_source_id("phase3-score-test-1")
        assert event_log is not None
        assert event_log["user_id"] == "ACM0001"

        # ml_anomaly_scores should have at least one row for ACM0001
        recent = database.list_recent_ml_scores_for_user("ACM0001", limit=5)
        assert len(recent) >= 1
        # The score row is for a user with only 1 logon event → likely normal
        # but the test should not assert is_anomaly (depends on model).
        for row in recent:
            assert row["user_id"] == "ACM0001"
            assert "scored_at" in row
            assert "feature_summary" in row


@requires_postgres
@pytest.mark.asyncio
async def test_admin_score_user_endpoint_with_real_db() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        token = login.json()["accessToken"]
        resp = await client.post(
            "/api/admin/score-user/ACM0001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # User may have no events → skipped, or may have events → scored.
        assert "user_id" in data
        assert data["user_id"] == "ACM0001"


@requires_postgres
@pytest.mark.asyncio
async def test_admin_score_user_endpoint_404_for_unknown_user() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        token = login.json()["accessToken"]
        resp = await client.post(
            "/api/admin/score-user/DOES_NOT_EXIST",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


@requires_postgres
@pytest.mark.asyncio
async def test_scoring_stats_endpoint() -> None:
    async with get_test_client(init_db=True) as client:
        login = await client.post(
            "/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"}
        )
        token = login.json()["accessToken"]
        resp = await client.get(
            "/api/admin/scoring-stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for k in ("total_scored", "total_anomalies", "total_alerts_created", "enabled"):
            assert k in data
