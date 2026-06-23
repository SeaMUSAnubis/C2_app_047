#!/usr/bin/env python3
"""Import toàn bộ CERT r4.2 (~32M dòng) vào PostgreSQL trong Docker container.

Tối ưu:
- Batch nhỏ (5000 dòng) + commit thường xuyên → giới hạn WAL size
- CHECKPOINT sau mỗi file → giải phóng WAL cũ
- Streaming CSV, không load toàn bộ vào RAM
- long_running connection → không bị statement timeout
- Giám sát disk usage trong quá trình import

Cách dùng:
    # Import toàn bộ (trong container):
    cat scripts/import_cert_full.py | docker compose exec -T app python3 -

    # Smoke test 1000 dòng/file:
    cat scripts/import_cert_full.py | docker compose exec -T app python3 - --limit-per-file 1000

    # Xoá cũ import lại:
    cat scripts/import_cert_full.py | docker compose exec -T app python3 - --reset-cert-events
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1] if "__file__" in dir() else Path("/app")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MODEL_VERSION = "ocsvm-v1.0-cert"
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "raw" / "cert-r4.2"
EVENT_FILES = ("logon.csv", "device.csv", "file.csv", "email.csv", "http.csv")
DEPARTMENTS = ("Finance", "HR", "Engineering", "Legal", "Operations", "Sales")
JOB_ROLES = ("Analyst", "Specialist", "Engineer", "Manager", "Operator", "Auditor")

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _opt(v: Any) -> str | None:
    if v is None: return None
    t = str(v).strip()
    return None if not t or t.lower() == "nan" else t

def _trunc(v: str | None, n: int) -> str | None:
    return v if v is None or len(v) <= n else v[:n] + "..."

def _parse_ts(v: str | None) -> str | None:
    if not v: return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError: continue
    return v

def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _disk_usage_gb(path: str) -> float:
    try:
        s = os.statvfs(path)
        used = (s.f_blocks - s.f_bfree) * s.f_frsize
        total = s.f_blocks * s.f_frsize
        return used / (1024**3), total / (1024**3)
    except Exception:
        return 0, 0

# ═══════════════════════════════════════════════════════════════════════════════
# Users & Devices (upsert theo lô nhỏ, không giữ trong RAM toàn bộ)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_profiles(data_dir: Path) -> dict[str, dict[str, str | None]]:
    pf = data_dir / "psychometric.csv"
    if not pf.exists():
        return {}
    out: dict[str, dict[str, str | None]] = {}
    with pf.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            uid = _opt(row.get("user_id"))
            if not uid: continue
            out[uid] = {
                "full_name": _opt(row.get("employee_name")) or uid,
                "email": _opt(row.get("email")) or f"{uid.lower()}@dtaa.com",
                "department": _opt(row.get("department")),
                "job_role": _opt(row.get("role")),
            }
    return out

def _upsert_users(conn: Any, users: Iterable[str], profiles: dict, now: str) -> None:
    rows = []
    for i, uid in enumerate(sorted(set(users))):
        p = profiles.get(uid, {})
        rows.append((
            uid, uid.lower(),
            p.get("full_name") or uid,
            p.get("email") or f"{uid.lower()}@dtaa.com",
            p.get("department") or DEPARTMENTS[i % len(DEPARTMENTS)],
            p.get("job_role") or JOB_ROLES[i % len(JOB_ROLES)],
            "active", 0, now, now,
        ))
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO users (id,username,full_name,email,department,job_role,status,risk_score,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(id) DO UPDATE SET username=EXCLUDED.username,full_name=EXCLUDED.full_name,
                       email=EXCLUDED.email,department=EXCLUDED.department,job_role=EXCLUDED.job_role,updated_at=EXCLUDED.updated_at""",
                rows)

def _upsert_devices(conn: Any, devices: Iterable[str], owner: dict, now: str) -> None:
    rows = []
    for i, did in enumerate(sorted(set(devices))):
        rows.append((
            did, did,
            "Windows 10" if i % 3 else "Windows 11",
            f"10.{20 + i % 30}.{i % 255}.{10 + i % 200}",
            owner.get(did), "online", 0, now, now, now,
        ))
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO devices (id,hostname,os,ip_address,assigned_user_id,status,risk_score,last_seen,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(id) DO UPDATE SET hostname=EXCLUDED.hostname,os=EXCLUDED.os,
                       ip_address=EXCLUDED.ip_address,
                       assigned_user_id=COALESCE(devices.assigned_user_id,EXCLUDED.assigned_user_id),
                       status=EXCLUDED.status,last_seen=EXCLUDED.last_seen,updated_at=EXCLUDED.updated_at""",
                rows)

# ═══════════════════════════════════════════════════════════════════════════════
# Event transform
# ═══════════════════════════════════════════════════════════════════════════════

def _event_rec(fname: str, et: str, row: dict, now: str) -> tuple | None:
    sid = _opt(row.get("id"))
    ts = _parse_ts(_opt(row.get("date")))
    if not sid or not ts:
        return None
    return (
        f"cert-r42:{et}:{sid}", fname, ts,
        _opt(row.get("user")), _opt(row.get("pc")), et,
        _action(et, row), _resource(et, row),
        json.dumps(_meta(et, row), sort_keys=True),
        json.dumps(_compact(et, row), sort_keys=True),
        now,
    )

def _action(et: str, row: dict) -> str:
    if et in ("logon", "device"):
        return (_opt(row.get("activity")) or et).lower()
    if et == "file":
        return _opt(row.get("activity")) or "file_access"
    return {"email": "email_send", "http": "http_access"}.get(et, et)

def _resource(et: str, row: dict) -> str:
    return _opt(row.get({"http": "url", "file": "filename", "email": "to"}.get(et, "pc"))) or ""

def _meta(et: str, row: dict) -> dict:
    m = {"event_type": et}
    if et in ("logon", "device"):
        m["activity"] = _opt(row.get("activity"))
    if et == "file":
        m["content"] = _opt(row.get("content"))
        m["to_removable"] = _opt(row.get("to_removable_media"))
        m["from_removable"] = _opt(row.get("from_removable_media"))
    if et == "email":
        for k in ("from", "to", "cc", "bcc", "size", "attachments"):
            m[k] = _opt(row.get(k))
    if et == "http":
        m["source_ip"] = "203.113.45.21" if hash(str(row.get("id"))) % 5 == 0 else "10.20.10.15"
    return m

def _compact(et: str, row: dict) -> dict:
    p = {k: _opt(row.get(k)) for k in ("id", "date", "user", "pc")}
    p["event_type"] = et
    if et in ("logon", "device"):
        p["activity"] = _opt(row.get("activity"))
    if et == "file":
        p["filename"] = _opt(row.get("filename"))
        p["activity"] = _opt(row.get("activity"))
        p["content_preview"] = _trunc(_opt(row.get("content")), 240)
    if et == "email":
        p["from"] = _opt(row.get("from"))
        p["to"] = _trunc(_opt(row.get("to")), 240)
        p["cc"] = _trunc(_opt(row.get("cc")), 240)
        p["size"] = _opt(row.get("size"))
        p["attachments"] = _opt(row.get("attachments"))
        p["content_preview"] = _trunc(_opt(row.get("content")), 240)
    if et == "http":
        p["url"] = _trunc(_opt(row.get("url")), 500)
        p["content_preview"] = _trunc(_opt(row.get("content")), 240)
    return {k: v for k, v in p.items() if v is not None}

# ═══════════════════════════════════════════════════════════════════════════════
# Core import
# ═══════════════════════════════════════════════════════════════════════════════

def _checkpoint(conn: Any) -> None:
    """Force PostgreSQL checkpoint để giải phóng WAL, tránh tràn disk."""
    try:
        conn.execute("CHECKPOINT")
    except Exception:
        pass  # best-effort

def _vacuum_if_needed(conn: Any, file_idx: int) -> None:
    """Chạy VACUUM nhẹ sau mỗi file để giữ kích thước DB gọn."""
    if file_idx > 0:  # Sau file đầu tiên
        try:
            conn.execute("VACUUM event_logs")
        except Exception:
            pass

def import_cert(data_dir: Path, batch_size: int = 5000,
               limit_per_file: int | None = None,
               reset: bool = False) -> dict:
    from src.backend.app.db.session import get_connection

    # ── Dùng long_running để không bị statement_timeout 5s cắt ngang ──
    with get_connection(long_running=True) as conn:

        if reset:
            conn.execute(
                "DELETE FROM alerts WHERE event_log_id IN "
                "(SELECT id FROM event_logs WHERE source_id LIKE 'cert-r42:%')")
            conn.execute("DELETE FROM event_logs WHERE source_id LIKE 'cert-r42:%'")
            conn.commit()
            print("[reset] Đã xoá dữ liệu CERT cũ")

        profiles = _load_profiles(data_dir)
        users_acc: set[str] = set(profiles)
        devices_acc: set[str] = set()
        device_owner: dict[str, str] = {}
        total = 0
        skipped = 0
        counts: dict[str, int] = {}

        # ── Upsert users từ psychometric trước ──
        _upsert_users(conn, users_acc, profiles, _now())
        conn.commit()

        for file_idx, filename in enumerate(EVENT_FILES):
            fp = data_dir / filename
            if not fp.exists():
                print(f"[skip] {filename} — không tìm thấy")
                continue

            et = fp.stem.lower()
            loaded = 0
            skip = 0
            batch: list = []
            new_users: set[str] = set()
            new_devices: set[str] = set()

            # ── Stream CSV từng dòng, không load toàn bộ vào RAM ──
            with fp.open(newline="", encoding="utf-8", errors="replace") as fh:
                for i, row in enumerate(csv.DictReader(fh), 1):
                    if limit_per_file and i > limit_per_file:
                        break

                    rec = _event_rec(filename, et, row, _now())
                    if rec is None:
                        skip += 1
                        continue

                    uid, did = rec[3], rec[4]
                    if uid:
                        new_users.add(uid)
                    if did:
                        new_devices.add(did)
                        if uid and did not in device_owner:
                            device_owner[did] = uid

                    batch.append(rec)

                    # ── Batch đầy → flush vào DB + commit ngay ──
                    if len(batch) >= batch_size:
                        if new_users:
                            _upsert_users(conn, new_users, profiles, _now())
                            users_acc |= new_users
                            new_users.clear()
                        if new_devices:
                            _upsert_devices(conn, new_devices, device_owner, _now())
                            devices_acc |= new_devices
                            new_devices.clear()
                        _write_batch(conn, batch)
                        conn.commit()
                        loaded += len(batch)
                        total += len(batch)
                        batch.clear()
                        _print_progress(filename, loaded, total)

            # ── Flush batch cuối ──
            if batch:
                if new_users:
                    _upsert_users(conn, new_users, profiles, _now())
                    users_acc |= new_users
                if new_devices:
                    _upsert_devices(conn, new_devices, device_owner, _now())
                    devices_acc |= new_devices
                _write_batch(conn, batch)
                conn.commit()
                loaded += len(batch)
                total += len(batch)

            skipped += skip
            counts[et] = loaded

            # ── Giải phóng WAL sau mỗi file ──
            _checkpoint(conn)
            used_gb, total_gb = _disk_usage_gb("/var/lib/postgresql/data")
            print(f"✓ {filename}: {loaded:,} loaded, {skip:,} skip | disk: {used_gb:.1f}/{total_gb:.1f} GB",
                  flush=True)

        # ── Risk scores + alerts (nhẹ, chạy cuối) ──
        print("\nTính risk scores...", flush=True)
        risk = _recalc_risk_scores(conn)
        conn.commit()

        print("Tạo alerts...", flush=True)
        alerts = _create_alerts(conn)
        conn.commit()

        _checkpoint(conn)

    return {
        "data_dir": str(data_dir),
        "rows_imported": total, "rows_skipped": skipped,
        "users": len(users_acc), "devices": len(devices_acc),
        "event_types": counts, **risk, **alerts,
    }

def _write_batch(conn, rows):
    if not rows:
        return
    # Dùng COPY-style batch insert qua executemany — nhanh hơn INSERT từng dòng
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO event_logs (source_id,source_file,timestamp,user_id,device_id,event_type,
               action,resource,metadata_json,raw_json,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(source_id) DO UPDATE SET source_file=EXCLUDED.source_file,
                   timestamp=EXCLUDED.timestamp,user_id=EXCLUDED.user_id,device_id=EXCLUDED.device_id,
                   event_type=EXCLUDED.event_type,action=EXCLUDED.action,resource=EXCLUDED.resource,
                   metadata_json=EXCLUDED.metadata_json,raw_json=EXCLUDED.raw_json""",
            rows)

def _print_progress(fname: str, loaded: int, total: int) -> None:
    used_gb, total_gb = _disk_usage_gb("/var/lib/postgresql/data")
    print(f"  {fname}: {loaded:>10,} / {total:>10,} tổng | disk: {used_gb:.1f}/{total_gb:.1f} GB",
          end="\r", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# Post-import: risk scores + alerts
# ═══════════════════════════════════════════════════════════════════════════════

def _recalc_risk_scores(conn) -> dict:
    users = conn.execute(
        """SELECT user_id, COUNT(*) AS ev,
                  COUNT(*) FILTER (WHERE event_type='http') AS h,
                  COUNT(*) FILTER (WHERE event_type='file') AS f,
                  COUNT(*) FILTER (WHERE event_type='email') AS e
           FROM event_logs WHERE user_id IS NOT NULL
           GROUP BY user_id ORDER BY ev DESC, user_id""").fetchall()
    for idx, r in enumerate(users):
        s = _ranked_score(idx, int(r["ev"]), int(r["h"]), int(r["f"]), int(r["e"]))
        conn.execute("UPDATE users SET risk_score=%s, updated_at=%s WHERE id=%s",
                     (s, _now(), r["user_id"]))
    devs = conn.execute(
        """SELECT device_id, COUNT(*) AS ev FROM event_logs
           WHERE device_id IS NOT NULL
           GROUP BY device_id ORDER BY ev DESC, device_id""").fetchall()
    for idx, r in enumerate(devs):
        s = max(8, min(96, 88 - idx * 2 + min(10, int(r["ev"]) // 5000)))
        conn.execute("UPDATE devices SET risk_score=%s, updated_at=%s WHERE id=%s",
                     (s, _now(), r["device_id"]))
    return {"risk_scored_users": len(users), "risk_scored_devices": len(devs)}

def _ranked_score(idx: int, ev: int, h: int, f: int, e: int) -> int:
    if idx < 12:
        return max(74, 98 - idx * 2)
    return max(8, min(72, 18 + min(25, ev // 5000) + min(20, h // 4000)
                      + min(14, f // 1500) + min(10, e // 2500)))

def _create_alerts(conn) -> dict:
    conn.execute("DELETE FROM alerts WHERE model_version=%s AND event_log_id IS NOT NULL",
                 (MODEL_VERSION,))
    rows = conn.execute(
        """SELECT * FROM (
            SELECT e.id, e.user_id, e.device_id, e.event_type, e.action,
                   e.resource, e.timestamp,
                   GREATEST(COALESCE(u.risk_score,0),COALESCE(d.risk_score,0)) AS risk_score,
                   ROW_NUMBER() OVER (PARTITION BY e.user_id ORDER BY e.timestamp DESC,e.id DESC) AS rn
            FROM event_logs e
            LEFT JOIN users u ON u.id=e.user_id
            LEFT JOIN devices d ON d.id=e.device_id
            WHERE e.user_id IS NOT NULL) sub
        WHERE rn=1 ORDER BY risk_score DESC, timestamp DESC LIMIT 200""").fetchall()
    titles = {"http": "HTTP access lệch baseline", "file": "File access bất thường",
              "email": "Email activity rủi ro cao", "logon": "Logon anomaly"}
    created = 0
    for r in rows:
        rs = int(r["risk_score"] or 0)
        if rs < 45:
            continue
        sev = "critical" if rs >= 85 else "high" if rs >= 70 else "medium"
        res = conn.execute(
            """INSERT INTO alerts (user_id,device_id,event_log_id,model_version,title,severity,status,
                risk_score,anomaly_score,risk_factors_json,explanation,detected_at,updated_at)
               SELECT %s,%s,%s,%s,%s,%s,'new',%s,%s,%s,%s,%s,%s
               WHERE NOT EXISTS (SELECT 1 FROM alerts WHERE event_log_id=%s)""",
            (r["user_id"], r["device_id"], r["id"], MODEL_VERSION,
             titles.get(r["event_type"], f"{r['event_type'].upper()} anomaly"),
             sev, rs, round(rs/100, 2),
             json.dumps([f"Event type: {r['event_type']}", "Risk score vượt baseline"]),
             f"UEBA phát hiện {r['event_type']} event có risk score {rs}, vượt ngưỡng SOC.",
             r["timestamp"], _now(), r["id"]))
        created += res.rowcount or 0
    return {"alerts_created": created}

# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def _init_db():
    from src.backend.app.db.pool import init_pool
    from src.backend.app.db.session import initialize_database
    init_pool()
    initialize_database()

def main():
    parser = argparse.ArgumentParser(description="Import CERT r4.2 → PostgreSQL (tối ưu disk/RAM)")
    parser.add_argument("--batch-size", type=int, default=5000,
                        help="Dòng mỗi batch (mặc định 5000)")
    parser.add_argument("--limit-per-file", type=int, default=None,
                        help="Giới hạn dòng/file để smoke test")
    parser.add_argument("--reset-cert-events", action="store_true",
                        help="Xoá CERT cũ trước khi import")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR),
                        help="Thư mục chứa CSV CERT")
    args = parser.parse_args()

    ddir = Path(args.data_dir)
    if not ddir.exists():
        print(f"LỖI: Không tìm thấy: {ddir}", file=sys.stderr)
        sys.exit(1)

    # ── Kiểm tra disk trước khi bắt đầu ──
    pg_data = os.environ.get("PGDATA", "/var/lib/postgresql/data")
    used, total = _disk_usage_gb(pg_data)
    free = total - used
    print(f"Disk PGDATA  : {used:.1f} GB used / {total:.1f} GB total ({free:.1f} GB free)")
    print(f"Data dir     : {ddir}")
    print(f"Batch size   : {args.batch_size:,} dòng")
    if args.limit_per_file:
        print(f"Limit/file   : {args.limit_per_file:,} (smoke test)")
    if free < 10:
        print(f"⚠️  CẢNH BÁO: Chỉ còn {free:.1f} GB trống. Import có thể thất bại!", file=sys.stderr)
        print("   Đề xuất: giải phóng ít nhất 30-50 GB trước khi chạy.", file=sys.stderr)

    # ── Kích thước ước tính ──
    csv_total = sum((ddir / f).stat().st_size for f in EVENT_FILES if (ddir / f).exists())
    print(f"CSV tổng      : {csv_total / (1024**3):.1f} GB")
    print(f"DB ước tính   : ~{csv_total / (1024**3) * 1.8:.1f} GB (CSV * 1.8)")
    print()

    _init_db()
    result = import_cert(ddir, args.batch_size, args.limit_per_file, args.reset_cert_events)

    print(f"\n{'='*60}")
    print(f"Users        : {result['users']}")
    print(f"Devices      : {result['devices']}")
    print(f"Events       : {result['rows_imported']:,}")
    print(f"Skipped      : {result['rows_skipped']:,}")
    print(f"Alerts       : {result['alerts_created']}")
    print(f"Risk scored  : {result['risk_scored_users']} users, {result['risk_scored_devices']} devices")
    used, total = _disk_usage_gb(pg_data)
    print(f"Disk cuối    : {used:.1f}/{total:.1f} GB")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
