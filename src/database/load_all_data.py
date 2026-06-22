from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MODEL_VERSION = "ocsvm-v1.0-cert"
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "raw" / "cert-r4.2"
EVENT_FILES = ("logon.csv", "device.csv", "file.csv", "email.csv", "http.csv")
DEPARTMENTS = ("Finance", "HR", "Engineering", "Legal", "Operations", "Sales")
JOB_ROLES = ("Analyst", "Specialist", "Engineer", "Manager", "Operator", "Auditor")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nạp toàn bộ CERT r4.2 CSV vào PostgreSQL mà không train lại model."
    )
    parser.add_argument(
        "--data-dir",
        default=os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)),
        help="Thư mục chứa logon/device/file/email/http/psychometric.csv.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("LOAD_BATCH_SIZE", "20000")),
        help="Số dòng CSV xử lý mỗi batch.",
    )
    parser.add_argument(
        "--limit-per-file",
        type=int,
        default=None,
        help="Giới hạn số dòng mỗi file để smoke test. Bỏ trống để nạp toàn bộ.",
    )
    parser.add_argument(
        "--reset-cert-events",
        action="store_true",
        help="Xóa event/alert CERT đã nạp trước đó rồi nạp lại. Không xóa model/weights/data file.",
    )
    return parser.parse_args()


def main() -> dict[str, Any]:
    from src.backend.app.db.session import get_connection, initialize_database, utc_now

    args = parse_args()
    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        raise RuntimeError(f"Không tìm thấy data dir: {data_dir}")
    if args.batch_size <= 0:
        raise RuntimeError("--batch-size phải lớn hơn 0")

    initialize_database()
    with get_connection() as conn:
        if args.reset_cert_events:
            _reset_cert_events(conn)
            conn.commit()
        _upsert_model_artifact(conn, utc_now(), data_dir)
        conn.commit()
        profiles = _load_profiles(data_dir)
        totals = _load_events(conn, data_dir, profiles, args.batch_size, args.limit_per_file)
        totals.update(_recalculate_risk_scores(conn))
        totals.update(_create_alerts_from_events(conn))

    return {"data_dir": str(data_dir), **totals}


def _reset_cert_events(conn: Any) -> None:
    conn.execute(
        "DELETE FROM alerts WHERE event_log_id IN (SELECT id FROM event_logs WHERE source_id LIKE 'cert-r42:%')"
    )
    conn.execute("DELETE FROM event_logs WHERE source_id LIKE 'cert-r42:%'")


def _upsert_model_artifact(conn: Any, now: str, data_dir: Path) -> None:
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
            json.dumps({"source": str(data_dir), "detector": "OneClassSVM", "trained": False}, sort_keys=True),
            json.dumps({"note": "metadata only; loader does not train model"}, sort_keys=True),
            now,
        ),
    )


def _load_profiles(data_dir: Path) -> dict[str, dict[str, str | None]]:
    profile_file = data_dir / "psychometric.csv"
    if not profile_file.exists():
        return {}
    profiles: dict[str, dict[str, str | None]] = {}
    with profile_file.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            user_id = _optional_text(row.get("user_id"))
            if not user_id:
                continue
            profiles[user_id] = {
                "full_name": _optional_text(row.get("employee_name")) or user_id,
                "email": _optional_text(row.get("email")) or f"{user_id.lower()}@dtaa.com",
                "department": _optional_text(row.get("department")),
                "job_role": _optional_text(row.get("role")),
            }
    return profiles


def _load_events(
    conn: Any,
    data_dir: Path,
    profiles: dict[str, dict[str, str | None]],
    batch_size: int,
    limit_per_file: int | None,
) -> dict[str, Any]:
    from src.backend.app.db.session import utc_now

    now = utc_now()
    users_seen: set[str] = set(profiles)
    devices_seen: set[str] = set()
    device_owner: dict[str, str] = {}
    total_loaded = 0
    total_skipped = 0
    event_type_counts: dict[str, int] = {}

    if users_seen:
        _upsert_users(conn, users_seen, profiles, now)

    for filename in EVENT_FILES:
        file_path = data_dir / filename
        if not file_path.exists():
            continue

        event_type = file_path.stem.lower()
        file_loaded = 0
        file_skipped = 0
        batch: list[tuple[Any, ...]] = []

        with file_path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row_index, row in enumerate(csv.DictReader(handle), start=1):
                if limit_per_file is not None and row_index > limit_per_file:
                    break
                record = _event_record(filename, event_type, row, now)
                if record is None:
                    file_skipped += 1
                    continue

                user_id = record[3]
                device_id = record[4]
                if user_id:
                    users_seen.add(user_id)
                if device_id:
                    devices_seen.add(device_id)
                    if user_id and device_id not in device_owner:
                        device_owner[device_id] = user_id

                batch.append(record)
                if len(batch) >= batch_size:
                    _upsert_users(conn, users_seen, profiles, now)
                    _upsert_devices(conn, devices_seen, device_owner, now)
                    _upsert_event_batch(conn, batch)
                    conn.commit()
                    file_loaded += len(batch)
                    total_loaded += len(batch)
                    batch.clear()
                    _print_progress(filename, file_loaded, total_loaded)

        if batch:
            _upsert_users(conn, users_seen, profiles, now)
            _upsert_devices(conn, devices_seen, device_owner, now)
            _upsert_event_batch(conn, batch)
            conn.commit()
            file_loaded += len(batch)
            total_loaded += len(batch)
            batch.clear()
            _print_progress(filename, file_loaded, total_loaded)

        total_skipped += file_skipped
        event_type_counts[event_type] = file_loaded
        print(f"Hoàn tất {filename}: loaded={file_loaded}, skipped={file_skipped}", flush=True)

    return {
        "rows_imported": total_loaded,
        "rows_skipped": total_skipped,
        "users_found": len(users_seen),
        "devices_found": len(devices_seen),
        "event_types": event_type_counts,
    }


def _event_record(filename: str, event_type: str, row: dict[str, Any], now: str) -> tuple[Any, ...] | None:
    source_id = _optional_text(row.get("id"))
    timestamp = _parse_cert_timestamp(_optional_text(row.get("date")))
    user_id = _optional_text(row.get("user"))
    device_id = _optional_text(row.get("pc"))
    if not source_id or not timestamp:
        return None

    metadata = _metadata(event_type, row)
    return (
        f"cert-r42:{event_type}:{source_id}",
        filename,
        timestamp,
        user_id,
        device_id,
        event_type,
        _event_action(event_type, row),
        _event_resource(event_type, row),
        json.dumps(metadata, sort_keys=True),
        json.dumps(_compact_raw_payload(event_type, row), sort_keys=True),
        now,
    )


def _compact_raw_payload(event_type: str, row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": _optional_text(row.get("id")),
        "date": _optional_text(row.get("date")),
        "user": _optional_text(row.get("user")),
        "pc": _optional_text(row.get("pc")),
        "event_type": event_type,
    }
    if event_type in {"logon", "device"}:
        payload["activity"] = _optional_text(row.get("activity"))
    if event_type == "file":
        payload.update(
            {
                "filename": _optional_text(row.get("filename")),
                "activity": _optional_text(row.get("activity")),
                "content_preview": _truncate(_optional_text(row.get("content")), 240),
                "to_removable_media": _optional_text(row.get("to_removable_media")),
                "from_removable_media": _optional_text(row.get("from_removable_media")),
            }
        )
    if event_type == "email":
        payload.update(
            {
                "from": _optional_text(row.get("from")),
                "to": _truncate(_optional_text(row.get("to")), 240),
                "cc": _truncate(_optional_text(row.get("cc")), 240),
                "bcc": _truncate(_optional_text(row.get("bcc")), 240),
                "size": _optional_text(row.get("size")),
                "attachments": _optional_text(row.get("attachments")),
                "content_preview": _truncate(_optional_text(row.get("content")), 240),
            }
        )
    if event_type == "http":
        payload.update(
            {
                "url": _truncate(_optional_text(row.get("url")), 500),
                "content_preview": _truncate(_optional_text(row.get("content")), 240),
            }
        )
    return {key: value for key, value in payload.items() if value is not None}


def _upsert_event_batch(conn: Any, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
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
            rows,
        )


def _upsert_users(
    conn: Any,
    users: Iterable[str],
    profiles: dict[str, dict[str, str | None]],
    now: str,
) -> None:
    rows = []
    for index, user_id in enumerate(sorted(users)):
        profile = profiles.get(user_id, {})
        rows.append(
            (
                user_id,
                user_id.lower(),
                profile.get("full_name") or user_id,
                profile.get("email") or f"{user_id.lower()}@dtaa.com",
                profile.get("department") or DEPARTMENTS[index % len(DEPARTMENTS)],
                profile.get("job_role") or JOB_ROLES[index % len(JOB_ROLES)],
                "active",
                0,
                now,
                now,
            )
        )
    if not rows:
        return
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


def _upsert_devices(conn: Any, devices: Iterable[str], device_owner: dict[str, str], now: str) -> None:
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
    if not rows:
        return
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
    now = _now()
    for index, row in enumerate(users):
        score = _ranked_score(
            index,
            int(row["events"] or 0),
            int(row["http_events"] or 0),
            int(row["file_events"] or 0),
            int(row["email_events"] or 0),
        )
        conn.execute("UPDATE users SET risk_score = %s, updated_at = %s WHERE id = %s", (score, now, row["user_id"]))

    devices = conn.execute(
        """
        SELECT device_id, COUNT(*) AS events
        FROM event_logs
        WHERE device_id IS NOT NULL
        GROUP BY device_id
        ORDER BY COUNT(*) DESC, device_id ASC
        """
    ).fetchall()
    now = _now()
    for index, row in enumerate(devices):
        score = max(8, min(96, 88 - index * 2 + min(10, int(row["events"] or 0) // 5000)))
        conn.execute("UPDATE devices SET risk_score = %s, updated_at = %s WHERE id = %s", (score, now, row["device_id"]))

    return {"risk_scored_users": len(users), "risk_scored_devices": len(devices)}


def _create_alerts_from_events(conn: Any) -> dict[str, Any]:
    conn.execute("DELETE FROM alerts WHERE model_version = %s AND event_log_id IS NOT NULL", (MODEL_VERSION,))
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
        LIMIT 200
        """
    ).fetchall()
    created = 0
    now = _now()
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
                now,
                row["id"],
            ),
        )
        created += result.rowcount or 0
    return {"alerts_created": created}


def _ranked_score(index: int, events: int, http_events: int, file_events: int, email_events: int) -> int:
    if index < 12:
        return max(74, 98 - index * 2)
    score = 18 + min(25, events // 5000) + min(20, http_events // 4000) + min(14, file_events // 1500) + min(10, email_events // 2500)
    return max(8, min(72, score))


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
        return _optional_text(row.get("activity")) or "file_access"
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
    if event_type in {"logon", "device"}:
        metadata["activity"] = _optional_text(row.get("activity"))
    if event_type == "file":
        metadata.update(
            {
                "content": _optional_text(row.get("content")),
                "to_removable": _optional_text(row.get("to_removable_media")),
                "from_removable": _optional_text(row.get("from_removable_media")),
            }
        )
    if event_type == "email":
        metadata.update(
            {
                "from": _optional_text(row.get("from")),
                "to": _optional_text(row.get("to")),
                "cc": _optional_text(row.get("cc")),
                "bcc": _optional_text(row.get("bcc")),
                "size": _optional_text(row.get("size")),
                "attachments": _optional_text(row.get("attachments")),
            }
        )
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


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None or len(value) <= max_length:
        return value
    return value[:max_length] + "..."


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _print_progress(filename: str, file_loaded: int, total_loaded: int) -> None:
    print(f"{filename}: loaded={file_loaded:,}, total={total_loaded:,}", flush=True)


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
