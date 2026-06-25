"""User-level ML scoring — gọi OCSVM trên event window của 1 user, persist score + alert.

Phase 3. Được trigger bởi:
- `normalizer.run_once(on_user_scored=...)` — sau khi batch raw logs được normalize.
- Admin endpoint `POST /api/admin/score-user/{user_id}` — manual re-score.

Flow:
1. Lấy event_logs của user trong lookback window.
2. Trích features bằng `DemoPipeline.extract_features` (đã có sẵn ở Phase 1).
3. Gọi OCSVM `run_ocsvm_inference(features_dict)` (CPU-bound, joblib).
4. Persist `ml_anomaly_scores` row.
5. Nếu anomaly + risk_score vượt ngưỡng → `create_alert` + LLM explain.
6. Update `ml_anomaly_scores.created_alert_id` với alert vừa tạo.

Sync helper — caller phải wrap trong `asyncio.to_thread` để không block loop.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

try:
    from datetime import UTC
except ImportError:  # pragma: no cover
    from datetime import timedelta as _td
    from datetime import timezone

    UTC = timezone(_td(0))

from src.backend.app.config import settings
from src.backend.app.db import session as database
from src.backend.app.services.demo_pipeline import demo_pipeline
from src.backend.app.services.llm import explain_alert
from src.ml.services.ueba_ml.inference import run_ocsvm_inference

logger = logging.getLogger(__name__)


@dataclass
class ScoringStats:
    total_scored: int = 0
    total_anomalies: int = 0
    total_alerts_created: int = 0
    total_errors: int = 0
    total_skipped_no_events: int = 0
    total_skipped_no_features: int = 0
    total_skipped_below_threshold: int = 0
    total_skipped_disabled: int = 0
    last_user_scored: str | None = None
    last_run_at: str | None = None
    recent: deque = field(default_factory=lambda: deque(maxlen=50))


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_minus_minutes_iso(minutes: int) -> str:
    return (
        (datetime.now(UTC) - timedelta(minutes=minutes))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _top_factors_from_features(feature_dict: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    """Pick top risk factors for alert title.

    Strategy: prefer factors that are non-zero in the feature vector AND have
    a clear semantic meaning. Fall back to "unusual_behavior_pattern" if the
    model flagged anomaly but no specific feature stood out.
    """
    factors: list[str] = []
    if feature_dict.get("n_file_exe", 0) and feature_dict.get("n_file_exe", 0) > 0:
        factors.append("executable_file_copy")
    if feature_dict.get("n_http_wikileaks", 0) and feature_dict.get("n_http_wikileaks", 0) > 0:
        factors.append("wikileaks_visit")
    if feature_dict.get("n_http_jobsearch", 0) and feature_dict.get("n_http_jobsearch", 0) > 0:
        factors.append("job_search_activity")
    if feature_dict.get("n_http_keylogger", 0) and feature_dict.get("n_http_keylogger", 0) > 0:
        factors.append("keylogger_related_traffic")
    if feature_dict.get("n_email", 0) and feature_dict.get("n_email", 0) >= 3:
        factors.append("high_email_volume")
    if feature_dict.get("n_device_afterhours", 0) and feature_dict.get("n_device_afterhours", 0) > 0:
        factors.append("after_hours_device")
    if feature_dict.get("n_logon_afterhours", 0) and feature_dict.get("n_logon_afterhours", 0) > 0:
        factors.append("after_hours_logon")
    if not factors:
        for e in events:
            if e.get("event_type") == "http" and e.get("action") == "blocked":
                factors.append("blocked_http_access")
                break
    if not factors:
        factors.append("unusual_behavior_pattern")
    return factors[:5]


def _severity_to_alert_severity(model_severity: str) -> str:
    """Map model severity to alert severity.

    Model severity is one of low/medium/high/critical — we use it directly
    but clamp unknown values to medium.
    """
    if model_severity in ("low", "medium", "high", "critical"):
        return model_severity
    return "medium"


class UserScoring:
    """Per-user OCSVM scoring + alert creation, with in-memory stats.

    `score_user` is sync (DB + joblib). The background loop in
    `normalizer_loop` calls it via `asyncio.to_thread`.

    A lock guards `stats` mutation so concurrent scorings don't trample
    the running counters.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats = ScoringStats()

    def reset_stats(self) -> None:
        """Reset in-memory stats. Used by tests; not for production code."""
        with self._lock:
            self._stats = ScoringStats()

    @property
    def stats(self) -> ScoringStats:
        return self._stats

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_scored": self._stats.total_scored,
                "total_anomalies": self._stats.total_anomalies,
                "total_alerts_created": self._stats.total_alerts_created,
                "total_errors": self._stats.total_errors,
                "total_skipped_no_events": self._stats.total_skipped_no_events,
                "total_skipped_no_features": self._stats.total_skipped_no_features,
                "total_skipped_below_threshold": self._stats.total_skipped_below_threshold,
                "total_skipped_disabled": self._stats.total_skipped_disabled,
                "last_user_scored": self._stats.last_user_scored,
                "last_run_at": self._stats.last_run_at,
                "recent": list(self._stats.recent)[-10:],
                "enabled": settings.ml_scoring_enabled,
                "window_minutes": settings.ml_scoring_window_minutes,
                "alert_min_risk": settings.ml_scoring_alert_min_risk,
            }

    def score_user(
        self,
        user_id: str,
        lookback_minutes: int | None = None,
        *,
        create_alert: bool = True,
    ) -> dict[str, Any]:
        """Score 1 user. Returns a dict describing the outcome.

        `create_alert=False` skips alert creation (useful for backfill where
        you only want to persist scores).
        """
        if not settings.ml_scoring_enabled:
            with self._lock:
                self._stats.total_skipped_disabled += 1
            return {"user_id": user_id, "skipped": True, "reason": "ml_scoring_disabled"}

        window = lookback_minutes or settings.ml_scoring_window_minutes
        since = _now_minus_minutes_iso(window)
        try:
            events = database.list_event_logs_for_user(user_id, since=since, limit=2000)
        except Exception as exc:
            logger.exception("user_scoring: list_event_logs_for_user failed for %s", user_id)
            with self._lock:
                self._stats.total_errors += 1
            return {"user_id": user_id, "error": f"list_events_failed: {exc}"}

        if not events:
            with self._lock:
                self._stats.total_skipped_no_events += 1
            return {"user_id": user_id, "skipped": True, "reason": "no_events_in_window"}

        # Extract features (DataFrame 1 row).
        try:
            # Flatten `raw` (and `metadata`) dicts into top-level so that the
            # demo pipeline's column-based extractors (filename, url, etc.) can
            # see the data — event_logs stores source payload as JSON columns,
            # not as flat top-level fields.
            flattened_events: list[dict[str, Any]] = []
            for e in events:
                flat_e = dict(e)
                for json_col in ("raw", "metadata"):
                    sub = flat_e.get(json_col)
                    if isinstance(sub, dict):
                        for k, v in sub.items():
                            if k not in flat_e:
                                flat_e[k] = v
                flattened_events.append(flat_e)
            features_df = demo_pipeline.extract_features(flattened_events)
        except Exception as exc:
            logger.exception("user_scoring: extract_features failed for %s", user_id)
            with self._lock:
                self._stats.total_errors += 1
            return {"user_id": user_id, "error": f"extract_features_failed: {exc}"}

        if features_df is None or features_df.empty:
            with self._lock:
                self._stats.total_skipped_no_features += 1
            return {"user_id": user_id, "skipped": True, "reason": "no_features"}

        feature_dict: dict[str, Any] = features_df.iloc[0].to_dict()
        # Normalise numpy types to Python primitives for JSON-serialisable storage.
        feature_summary = {k: (float(v) if hasattr(v, "item") else v) for k, v in feature_dict.items()}

        # OCSVM inference.
        try:
            infer = run_ocsvm_inference(feature_dict)
        except Exception as exc:
            logger.exception("user_scoring: run_ocsvm_inference failed for %s", user_id)
            with self._lock:
                self._stats.total_errors += 1
            return {"user_id": user_id, "error": f"inference_failed: {exc}"}

        scored_at = _utc_now_iso()
        device_id = events[-1].get("device_id") if events else None

        alert_id: int | None = None
        explanation: str | None = None
        if infer.is_anomaly and create_alert and infer.risk_score >= settings.ml_scoring_alert_min_risk:
            top_factors = _top_factors_from_features(feature_dict, events)
            title = (
                f"Suspicious Behavior: {', '.join(top_factors)}"
                if top_factors
                else "Suspicious Behavior Detected"
            )
            # Build LLM context (mirrors what demo_pipeline.analyze sends).
            timeline_parts: list[str] = []
            for e in events[-30:]:
                t = e.get("timestamp", "")
                a = e.get("action") or e.get("event_type", "")
                timeline_parts.append(f"{t}: {a}")
            timeline = "\n  ".join(timeline_parts) if timeline_parts else "no timeline"
            llm_context = {
                "user_id": user_id,
                "device_id": device_id or "UNKNOWN",
                "severity": infer.severity,
                "risk_score": infer.risk_score,
                "anomaly_score": infer.anomaly_score,
                "top_features": top_factors,
                "baseline": {},
                "timeline": f"  {timeline}",
            }
            try:
                explanation = explain_alert(llm_context)
            except Exception:
                logger.exception("user_scoring: explain_alert failed for %s", user_id)
                explanation = None
            alert_payload = {
                "user_id": user_id,
                "device_id": device_id,
                "model_version": infer.model_version,
                "title": title,
                "severity": _severity_to_alert_severity(infer.severity),
                "risk_score": int(infer.risk_score),
                "anomaly_score": float(infer.anomaly_score) if infer.anomaly_score is not None else None,
                "risk_factors": top_factors,
                "explanation": explanation,
                "status": "new",
            }
            try:
                created = database.create_alert(alert_payload)
                alert_id = int(created["id"])
            except Exception:
                logger.exception("user_scoring: create_alert failed for %s", user_id)
                alert_id = None
        elif infer.is_anomaly and (
            not create_alert or infer.risk_score < settings.ml_scoring_alert_min_risk
        ):
            with self._lock:
                self._stats.total_skipped_below_threshold += 1

        # Persist ml_anomaly_scores (always, even when no alert is created).
        score_payload = {
            "user_id": user_id,
            "device_id": device_id,
            "model_version": infer.model_version,
            "is_anomaly": bool(infer.is_anomaly),
            "anomaly_score": float(infer.anomaly_score) if infer.anomaly_score is not None else None,
            "risk_score": int(infer.risk_score) if infer.risk_score is not None else None,
            "severity": infer.severity,
            "feature_summary": feature_summary,
            "created_alert_id": alert_id,
            "scored_at": scored_at,
        }
        try:
            database.insert_ml_anomaly_score(score_payload)
        except Exception:
            logger.exception("user_scoring: insert_ml_anomaly_score failed for %s", user_id)
            with self._lock:
                self._stats.total_errors += 1

        outcome = {
            "user_id": user_id,
            "scored_at": scored_at,
            "is_anomaly": bool(infer.is_anomaly),
            "anomaly_score": float(infer.anomaly_score) if infer.anomaly_score is not None else None,
            "risk_score": int(infer.risk_score) if infer.risk_score is not None else None,
            "severity": infer.severity,
            "alert_created": alert_id is not None,
            "alert_id": alert_id,
            "events_used": len(events),
        }
        with self._lock:
            self._stats.total_scored += 1
            if infer.is_anomaly:
                self._stats.total_anomalies += 1
            if alert_id is not None:
                self._stats.total_alerts_created += 1
            self._stats.last_user_scored = user_id
            self._stats.last_run_at = scored_at
            self._stats.recent.append(
                {
                    "user_id": user_id,
                    "is_anomaly": bool(infer.is_anomaly),
                    "risk_score": int(infer.risk_score) if infer.risk_score is not None else None,
                    "alert_created": alert_id is not None,
                    "scored_at": scored_at,
                }
            )
        return outcome


# Module-level singleton.
user_scoring = UserScoring()


def get_user_scoring() -> UserScoring:
    return user_scoring
