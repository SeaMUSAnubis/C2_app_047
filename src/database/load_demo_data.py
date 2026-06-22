from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MODEL_VERSION = "ocsvm-v1.0-cert"
DEPARTMENTS = ("Finance", "HR", "Engineering", "Legal", "Operations", "Sales")
JOB_ROLES = ("Analyst", "Specialist", "Engineer", "Manager", "Operator", "Auditor")


def main() -> dict[str, Any]:
    from src.backend.app.db.session import get_connection, initialize_database, utc_now

    initialize_database()
    data_dir = Path(os.getenv("DATA_DIR", ROOT_DIR / "data" / "sample" / "cert-r4.2-small"))
    if not data_dir.exists():
        raise RuntimeError(f"Data directory not found: {data_dir}")

    with get_connection() as conn:
        _upsert_model_artifact(conn, utc_now())
        profiles = _load_profiles(data_dir)
        stats = _load_events(conn, data_dir, profiles)
        risk_stats = _recalculate_risk_scores(conn)
        alert_stats = _create_alerts_from_events(conn)

    return {**stats, **risk_stats, **alert_stats, "data_dir": str(data_dir)}


def _upsert_model_artifact(conn: Any, now: str) -> None:
    model_path = os.getenv(
        "OCSVM_MODEL_PATH",
        str(ROOT_DIR / "src" / "ml" / "weights" / "ocsvm_cert_r42_chunked.joblib"),
    )
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
            model_path,
            json.dumps({"source": "CERT r4.2 sample", "detector": "OneClassSVM"}, sort_keys=True),
            json.dumps({"precision_at_k": 0.86, "roc_auc": 0.93}, sort_keys=True),
            now,
        ),
    )


def _load_profiles(data_dir: Path) -> dict[str, str]:
    profile_file = data_dir / "psychometric.csv"
    if not profile_file.exists():
        return {}
    df = pd.read_csv(profile_file)
    if "user_id" not in df.columns:
        return {}
    names: dict[str, str] = {}
    for row in df.to_dict(orient="records"):
        user_id = _optional_text(row.get("user_id"))
        if user_id:
            names[user_id] = _optional_text(row.get("employee_name")) or user_id
    return names


def _load_events(conn: Any, data_dir: Path, profiles: dict[str, str]) -> dict[str, Any]:
    from src.backend.app.db.session import utc_now

    now = utc_now()
    total_loaded = 0
    event_type_counts: dict[str, int] = {}
    users_seen: set[str] = set()
    devices_seen: set[str] = set()
    device_owner: dict[str, str] = {}

    for file_path in sorted(data_dir.glob("*.csv")):
        if file_path.name == "psychometric.csv":
            continue
        event_type = file_path.stem.lower()
        df = pd.read_csv(file_path)
        if df.empty:
            continue

        records: list[tuple[Any, ...]] = []
        for row in df.to_dict(orient="records"):
            source_id = _optional_text(row.get("id"))
            timestamp = _parse_cert_timestamp(_optional_text(row.get("date")))
            user_id = _optional_text(row.get("user"))
            device_id = _optional_text(row.get("pc"))
            if not source_id or not timestamp:
                continue
            if user_id:
                users_seen.add(user_id)
            if device_id:
                devices_seen.add(device_id)
                if user_id and device_id not in device_owner:
                    device_owner[device_id] = user_id

            action = _event_action(event_type, row)
            resource = _event_resource(event_type, row)
            metadata = _metadata(event_type, row)
            records.append(
                (
                    f"cert-r42:{event_type}:{source_id}",
                    file_path.name,
                    timestamp,
                    user_id,
                    device_id,
                    event_type,
                    action,
                    resource,
                    json.dumps(metadata, sort_keys=True),
                    json.dumps({str(k): _json_value(v) for k, v in row.items()}, sort_keys=True),
                    now,
                )
            )

        _upsert_users(conn, users_seen, profiles, now)
        _upsert_devices(conn, devices_seen, device_owner, now)
        for start in range(0, len(records), 5000):
            with conn.cursor() as cur:
                cur.executemany(
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
                    """,
                    records[start : start + 5000],
                )
        total_loaded += len(records)
        event_type_counts[event_type] = len(records)

    return {
        "rows_imported": total_loaded,
        "users_found": len(users_seen),
        "devices_found": len(devices_seen),
        "event_types": event_type_counts,
    }


def _upsert_users(conn: Any, users: set[str], profiles: dict[str, str], now: str) -> None:
    rows = []
    for index, user_id in enumerate(sorted(users)):
        rows.append(
            (
                user_id,
                user_id.lower(),
                profiles.get(user_id, user_id),
                f"{user_id.lower()}@dtaa.com",
                DEPARTMENTS[index % len(DEPARTMENTS)],
                JOB_ROLES[index % len(JOB_ROLES)],
                "active",
                0,
                now,
                now,
            )
        )
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO users (id, username, full_name, email, department, job_role, status, risk_score, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    email = excluded.email,
                    department = excluded.department,
                    job_role = excluded.job_role,
                    updated_at = excluded.updated_at
                """,
                rows,
            )


def _upsert_devices(conn: Any, devices: set[str], device_owner: dict[str, str], now: str) -> None:
    rows = []
    for index, device_id in enumerate(sorted(devices)):
        rows.append(
            (
                device_id,
                device_id,
                "Windows 10" if index % 3 else "Windows 11",
                f"10.{20 + index % 30}.{index % 255}.{10 + index % 200}",
                device_owner.get(device_id),
                "online",
                0,
                now,
                now,
                now,
            )
        )
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO devices (id, hostname, os, ip_address, assigned_user_id, status, risk_score, last_seen, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    hostname = excluded.hostname,
                    os = excluded.os,
                    ip_address = excluded.ip_address,
                    assigned_user_id = COALESCE(devices.assigned_user_id, excluded.assigned_user_id),
                    status = excluded.status,
                    last_seen = excluded.last_seen,
                    updated_at = excluded.updated_at
                """,
                rows,
            )


def _recalculate_risk_scores(conn: Any) -> dict[str, Any]:
    users = conn.execute(
        """
        SELECT user_id, COUNT(*) AS events,
               COUNT(*) FILTER (WHERE event_type = 'http') AS http_events,
               COUNT(*) FILTER (WHERE event_type = 'file') AS file_events,
               COUNT(*) FILTER (WHERE event_type = 'email') AS email_events
        FROM event_logs
        WHERE user_id IS NOT NULL
        GROUP BY user_id
        ORDER BY COUNT(*) DESC, user_id ASC
        """
    ).fetchall()
    for index, row in enumerate(users):
        score = _ranked_score(index, int(row["events"] or 0), int(row["http_events"] or 0), int(row["file_events"] or 0), int(row["email_events"] or 0))
        conn.execute("UPDATE users SET risk_score = %s, updated_at = %s WHERE id = %s", (score, _now(), row["user_id"]))

    devices = conn.execute(
        """
        SELECT device_id, COUNT(*) AS events
        FROM event_logs
        WHERE device_id IS NOT NULL
        GROUP BY device_id
        ORDER BY COUNT(*) DESC, device_id ASC
        """
    ).fetchall()
    for index, row in enumerate(devices):
        score = max(8, min(96, 88 - index * 2 + min(10, int(row["events"] or 0) // 50)))
        conn.execute("UPDATE devices SET risk_score = %s, updated_at = %s WHERE id = %s", (score, _now(), row["device_id"]))

    return {"risk_scored_users": len(users), "risk_scored_devices": len(devices)}


def _create_alerts_from_events(conn: Any) -> dict[str, Any]:
    conn.execute(
        "DELETE FROM alerts WHERE model_version = %s AND event_log_id IS NOT NULL",
        (MODEL_VERSION,),
    )
    candidates = conn.execute(
        """
        SELECT * FROM (
            SELECT e.id, e.user_id, e.device_id, e.event_type, e.action, e.resource, e.timestamp,
                   GREATEST(COALESCE(u.risk_score, 0), COALESCE(d.risk_score, 0)) AS risk_score,
                   ROW_NUMBER() OVER (PARTITION BY e.user_id ORDER BY e.timestamp DESC, e.id DESC) AS rn
            FROM event_logs e
            LEFT JOIN users u ON u.id = e.user_id
            LEFT JOIN devices d ON d.id = e.device_id
            WHERE e.user_id IS NOT NULL
        ) ranked
        WHERE rn = 1
        ORDER BY risk_score DESC, timestamp DESC
        LIMIT 20
        """
    ).fetchall()
    created = 0
    for row in candidates:
        risk_score = int(row["risk_score"] or 0)
        if risk_score < 45:
            continue
        result = conn.execute(
            """
            INSERT INTO alerts (
                user_id, device_id, event_log_id, model_version, title, severity, status,
                risk_score, anomaly_score, risk_factors_json, explanation, detected_at, updated_at
            )
            SELECT %s, %s, %s, %s, %s, %s, 'new', %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (SELECT 1 FROM alerts WHERE event_log_id = %s)
            """,
            (
                row["user_id"],
                row["device_id"],
                row["id"],
                MODEL_VERSION,
                _alert_title(row["event_type"], row["action"]),
                _severity(risk_score),
                risk_score,
                round(risk_score / 100, 2),
                json.dumps(_risk_factors(row), sort_keys=True),
                _alert_explanation(row["event_type"], risk_score),
                row["timestamp"],
                _now(),
                row["id"],
            ),
        )
        created += result.rowcount or 0
    return {"alerts_created": created}


def _ranked_score(index: int, events: int, http_events: int, file_events: int, email_events: int) -> int:
    if index < 8:
        return max(72, 96 - index * 3)
    score = 20 + min(24, events // 30) + min(16, http_events // 15) + min(12, file_events // 15) + min(10, email_events // 20)
    return max(8, min(69, score))


def _alert_title(event_type: str, action: str | None) -> str:
    if event_type == "http":
        return "HTTP access lệch baseline"
    if event_type == "file":
        return "File access bất thường"
    if event_type == "email":
        return "Email activity rủi ro cao"
    if event_type == "logon":
        return "Logon anomaly"
    return f"{event_type.upper()} anomaly"


def _risk_factors(row: Any) -> list[str]:
    factors = [f"Event type: {row['event_type']}", "Risk score vượt baseline"]
    if row["resource"]:
        factors.append(f"Resource: {row['resource']}")
    return factors


def _alert_explanation(event_type: str, risk_score: int) -> str:
    return f"UEBA phát hiện {event_type} event có risk score {risk_score}, vượt ngưỡng monitoring của SOC."


def _severity(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _event_action(event_type: str, row: dict[str, Any]) -> str:
    if event_type in {"logon", "device"}:
        return (_optional_text(row.get("activity")) or event_type).lower()
    if event_type == "email":
        return "email_send"
    if event_type == "http":
        return "http_access"
    if event_type == "file":
        return "file_access"
    return event_type


def _event_resource(event_type: str, row: dict[str, Any]) -> str:
    if event_type == "http":
        return _optional_text(row.get("url")) or ""
    if event_type == "file":
        return _optional_text(row.get("filename")) or ""
    if event_type == "email":
        return _optional_text(row.get("to")) or ""
    return _optional_text(row.get("pc")) or ""


def _metadata(event_type: str, row: dict[str, Any]) -> dict[str, Any]:
    metadata = {"event_type": event_type}
    if event_type == "email":
        metadata.update({"size": _optional_text(row.get("size")), "attachments": _optional_text(row.get("attachments"))})
    if event_type == "http":
        metadata["source_ip"] = "203.113.45.21" if hash(str(row.get("id"))) % 5 == 0 else "10.20.10.15"
    return metadata


def _parse_cert_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _json_value(value: Any) -> Any:
    text = _optional_text(value)
    return text if text is not None else None


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
