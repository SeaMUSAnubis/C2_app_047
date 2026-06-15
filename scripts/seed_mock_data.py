from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MODEL_VERSION = "iForest-v0.1-demo"


EVENTS: list[dict[str, Any]] = [
    {
        "source_id": "demo:logon:1",
        "source_file": "logon.csv",
        "timestamp": "2026-06-15T08:05:00Z",
        "user_id": "BTR0002",
        "device_id": "PC-2002",
        "event_type": "logon",
        "action": "LOGIN_SUCCESS",
        "resource": "ENG-LT-2002",
        "metadata": {"geo": "VN-HCM", "risk_context": "normal office hour"},
        "raw": {"detail": "Successful login from assigned engineering laptop"},
    },
    {
        "source_id": "demo:file:1",
        "source_file": "file.csv",
        "timestamp": "2026-06-15T08:27:00Z",
        "user_id": "BTR0002",
        "device_id": "PC-2002",
        "event_type": "file",
        "action": "FILE_COPY_USB",
        "resource": "/finance/q2-payroll.xlsx",
        "metadata": {"bytes": 1843200, "sensitive": True},
        "raw": {"detail": "Copied payroll workbook to removable media"},
    },
    {
        "source_id": "demo:http:1",
        "source_file": "http.csv",
        "timestamp": "2026-06-15T08:35:00Z",
        "user_id": "BTR0002",
        "device_id": "PC-2002",
        "event_type": "http",
        "action": "HTTP_UPLOAD",
        "resource": "https://files.example-upload.test/drop",
        "metadata": {"bytes": 1843200, "category": "file_sharing"},
        "raw": {"detail": "Uploaded file to external sharing domain"},
    },
    {
        "source_id": "demo:logon:2",
        "source_file": "logon.csv",
        "timestamp": "2026-06-15T09:12:00Z",
        "user_id": "ACM0001",
        "device_id": "PC-1001",
        "event_type": "logon",
        "action": "LOGIN_SUCCESS",
        "resource": "FIN-WS-1001",
        "metadata": {"geo": "VN-HN", "risk_context": "known workstation"},
        "raw": {"detail": "Successful login from finance workstation"},
    },
    {
        "source_id": "demo:email:1",
        "source_file": "email.csv",
        "timestamp": "2026-06-15T09:41:00Z",
        "user_id": "ACM0001",
        "device_id": "PC-1001",
        "event_type": "email",
        "action": "EMAIL_ATTACHMENT_SENT",
        "resource": "external-recipient@example.test",
        "metadata": {"attachments": 2, "external_recipients": 1},
        "raw": {"detail": "Sent finance report attachments to external recipient"},
    },
    {
        "source_id": "demo:device:1",
        "source_file": "device.csv",
        "timestamp": "2026-06-15T10:03:00Z",
        "user_id": "CNL0003",
        "device_id": "PC-3003",
        "event_type": "device",
        "action": "USB_INSERT",
        "resource": "Kingston DataTraveler",
        "metadata": {"serial": "DEMO-USB-001"},
        "raw": {"detail": "USB device inserted on HR workstation"},
    },
]


ALERTS: list[dict[str, Any]] = [
    {
        "source_id": "demo:file:1",
        "title": "[demo] Sensitive file copied to removable media",
        "severity": "critical",
        "status": "new",
        "risk_score": 91,
        "anomaly_score": 0.97,
        "risk_factors": ["sensitive_file", "removable_media", "unusual_user_department"],
        "explanation": "Engineering user copied a finance payroll file to removable media.",
    },
    {
        "source_id": "demo:http:1",
        "title": "[demo] External upload after sensitive file access",
        "severity": "high",
        "status": "investigating",
        "risk_score": 86,
        "anomaly_score": 0.91,
        "risk_factors": ["external_upload", "file_sharing_domain", "temporal_correlation"],
        "explanation": "External upload occurred shortly after sensitive file copy activity.",
    },
    {
        "source_id": "demo:email:1",
        "title": "[demo] Finance attachment sent externally",
        "severity": "medium",
        "status": "new",
        "risk_score": 64,
        "anomaly_score": 0.62,
        "risk_factors": ["external_recipient", "attachment"],
        "explanation": "Finance report attachments were sent to an external recipient.",
    },
]


def main() -> None:
    from src.services.database import get_connection, initialize_database, utc_now

    initialize_database()
    now = utc_now()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO model_artifacts (
                model_version, artifact_path, training_config_json, metrics_json, created_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(model_version) DO UPDATE SET
                artifact_path = excluded.artifact_path,
                training_config_json = excluded.training_config_json,
                metrics_json = excluded.metrics_json
            """,
            (
                MODEL_VERSION,
                "artifacts/models/iforest_model.joblib",
                json.dumps({"source": "demo_mock_data", "detector": "IsolationForest"}),
                json.dumps({"precision_at_k": 0.83, "roc_auc": 0.91}),
                now,
            ),
        )

        event_ids: dict[str, int] = {}
        for event in EVENTS:
            row = conn.execute(
                """
                INSERT INTO event_logs (
                    source_id, source_file, timestamp, user_id, device_id, event_type,
                    action, resource, metadata_json, raw_json, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_file = excluded.source_file,
                    timestamp = excluded.timestamp,
                    user_id = excluded.user_id,
                    device_id = excluded.device_id,
                    event_type = excluded.event_type,
                    action = excluded.action,
                    resource = excluded.resource,
                    metadata_json = excluded.metadata_json,
                    raw_json = excluded.raw_json
                RETURNING id
                """,
                (
                    event["source_id"],
                    event["source_file"],
                    event["timestamp"],
                    event["user_id"],
                    event["device_id"],
                    event["event_type"],
                    event["action"],
                    event["resource"],
                    json.dumps(event["metadata"], sort_keys=True),
                    json.dumps(event["raw"], sort_keys=True),
                    now,
                ),
            ).fetchone()
            event_ids[event["source_id"]] = int(row["id"])

        conn.execute("DELETE FROM alerts WHERE title LIKE '[demo]%'")
        for alert in ALERTS:
            source_event = next(e for e in EVENTS if e["source_id"] == alert["source_id"])
            conn.execute(
                """
                INSERT INTO alerts (
                    user_id, device_id, event_log_id, model_version, title, severity,
                    status, risk_score, anomaly_score, risk_factors_json, explanation,
                    detected_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_event["user_id"],
                    source_event["device_id"],
                    event_ids[alert["source_id"]],
                    MODEL_VERSION,
                    alert["title"],
                    alert["severity"],
                    alert["status"],
                    alert["risk_score"],
                    alert["anomaly_score"],
                    json.dumps(alert["risk_factors"], sort_keys=True),
                    alert["explanation"],
                    source_event["timestamp"],
                    now,
                ),
            )

    print(
        "Seeded demo data: "
        f"{len(EVENTS)} event logs, {len(ALERTS)} alerts, model {MODEL_VERSION}"
    )


if __name__ == "__main__":
    main()
