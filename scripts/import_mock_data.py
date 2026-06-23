"""Import the mock dataset (data/mock/) into the running backend.

Two modes:

A) API mode (default, recommended) — uses the backend's HTTP API. This is
   the same path a real endpoint agent would use, so it also exercises the
   auth + /api/users, /api/devices, /api/logs/ingest endpoints. Requires a
   running backend and admin credentials.

       python scripts/import_mock_data.py
       python scripts/import_mock_data.py --server-url http://localhost:5173

B) Direct DB mode — inserts directly via psycopg. Use this when the
   backend HTTP stack is broken but PostgreSQL is up.

       python scripts/import_mock_data.py --direct

After import, you can:
- Open the dashboard (http://localhost:5173) and browse Users/Devices/Logs.
- Run ML scoring via the UI's "Analyze" button, OR call
    POST /api/demo/analyze-all
  via curl/Postman to trigger OCSVM scoring + alert generation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# MOCK_DIR resolution: prefer the repo's data/mock, but allow override via env
# var or CLI arg so the script can be run from anywhere (e.g. inside a
# container that mounts only a subset of the repo).
MOCK_DIR = Path(os.environ.get("MOCK_DATA_DIR", ROOT / "data" / "mock"))


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        import csv
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# LDAP / user mapping
# ---------------------------------------------------------------------------


def _load_users() -> list[dict]:
    """Read LDAP CSV and return the user list."""
    ldap_files = sorted((MOCK_DIR / "LDAP").glob("*.csv"))
    if not ldap_files:
        raise RuntimeError(f"No LDAP CSV in {MOCK_DIR / 'LDAP'}")
    with ldap_files[0].open("r", newline="", encoding="utf-8") as f:
        import csv
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({
            "id": r["user_id"].strip(),
            "username": r["user_id"].strip().lower(),
            "full_name": r["employee_name"].strip(),
            "email": r["email"].strip(),
            "department": r["department"].strip(),
            "job_role": r["role"].strip(),
            "team": r.get("team", "").strip() or None,
            "supervisor": r.get("supervisor", "").strip() or None,
        })
    return out


def _load_devices() -> list[dict]:
    """Derive device list from logon.csv + http.csv (any pc we see)."""
    seen: dict[str, set[str]] = {}
    for f in (MOCK_DIR / "logon.csv", MOCK_DIR / "http.csv",
              MOCK_DIR / "file.csv", MOCK_DIR / "email.csv",
              MOCK_DIR / "device.csv"):
        for row in _read_csv(f):
            pc = row.get("pc", "").strip()
            user = row.get("user", "").strip()
            if pc and user:
                seen.setdefault(pc, set()).add(user)
    out = []
    for pc, users in sorted(seen.items()):
        primary = sorted(users)[0]  # deterministic
        out.append({
            "id": pc,
            "hostname": f"WS-{pc}",
            "os": "Linux/Windows",
            "ip_address": f"10.20.10.{len(out) + 10}",
            "assigned_user_id": primary,
        })
    return out


def _parse_date(s: str) -> str:
    """Convert MM/DD/YYYY HH:MM:SS → ISO 8601 UTC (Z)."""
    from datetime import datetime
    s = s.strip()
    if not s:
        return ""
    try:
        dt = datetime.strptime(s, "%m/%d/%Y %H:%M:%S")
    except ValueError:
        # Already in ISO format maybe.
        return s
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Event transformation
# ---------------------------------------------------------------------------


def _events_for(event_type: str) -> list[dict]:
    """Read a mock CSV and transform rows into EventIngest dicts."""
    rows = _read_csv(MOCK_DIR / f"{event_type}.csv")
    out = []
    for r in rows:
        sid = f"mock:{event_type}:{r['id']}"
        action = (r.get("activity") or "").lower() or None
        if event_type == "logon":
            resource = r.get("pc")
        elif event_type == "http":
            resource = r.get("url")
        elif event_type == "file":
            resource = r.get("filename")
        elif event_type == "email":
            resource = r.get("to")
        elif event_type == "device":
            resource = r.get("pc")
        else:
            resource = None
        out.append({
            "source_id": sid,
            "source_file": f"mock/{event_type}.csv",
            "timestamp": _parse_date(r["date"]),
            "user_id": r.get("user") or None,
            "device_id": r.get("pc") or None,
            "event_type": event_type,
            "action": action,
            "resource": resource,
            "metadata": {"synthetic": True, "dataset": "mock"},
            "raw": r,
        })
    return out


# ---------------------------------------------------------------------------
# API mode
# ---------------------------------------------------------------------------


def import_via_api(server_url: str, email: str, password: str,
                   batch_size: int = 200, verbose: bool = True) -> dict:
    import httpx

    base = server_url.rstrip("/")
    out: dict[str, Any] = {"users": 0, "users_existed": 0, "devices": 0, "devices_existed": 0, "logs": 0, "errors": []}

    with httpx.Client(base_url=base, timeout=30.0) as client:
        # 1. Login.
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            raise RuntimeError(f"Login failed: {r.status_code} {r.text[:200]}")
        token = r.json()["accessToken"]
        h = {"Authorization": f"Bearer {token}"}

        # 2. Users.
        users_existed = 0
        for u in _load_users():
            r = client.post("/api/users", headers=h, json=u)
            if r.status_code in (200, 201):
                out["users"] += 1
            elif r.status_code == 409:
                users_existed += 1
                out["users_existed"] += 1
            else:
                out["errors"].append(f"user {u['id']}: {r.status_code} {r.text[:120]}")
        if verbose:
            parts = [f"{out['users']} mới"]
            if users_existed:
                parts.append(f"{users_existed} đã tồn tại")
            print(f"  Users: {', '.join(parts)}")

        # 3. Devices.
        devices_existed = 0
        for d in _load_devices():
            r = client.post("/api/devices", headers=h, json=d)
            if r.status_code in (200, 201):
                out["devices"] += 1
            elif r.status_code == 409:
                devices_existed += 1
                out["devices_existed"] += 1
            else:
                out["errors"].append(f"device {d['id']}: {r.status_code} {r.text[:120]}")
        if verbose:
            parts = [f"{out['devices']} mới"]
            if devices_existed:
                parts.append(f"{devices_existed} đã tồn tại")
            print(f"  Devices: {', '.join(parts)}")

        # 4. Events: read each CSV, ingest in batches.
        # Backend exposes only single POST /api/logs/ingest; for bulk we use
        # /api/raw-logs/batch which is the agent-style endpoint. Since raw
        # logs are unprocessed (no normalizer in Phase 1), we use the
        # single-event endpoint and chunk to keep server latency low.
        for et in ("logon", "device", "file", "http", "email"):
            events = _events_for(et)
            if verbose:
                print(f"  {et}: {len(events)} events, posting in batches of {batch_size}...")
            for i in range(0, len(events), batch_size):
                chunk = events[i:i + batch_size]
                # Backend expects the EventIngest body directly (no wrapper).
                # Send one-by-one for compatibility (server has no batch for
                # event_logs yet). The loop is fast: ~1000 events ≈ 30s.
                accepted = 0
                last_err = None
                for ev in chunk:
                    r = client.post("/api/logs/ingest", headers=h, json=ev)
                    if r.status_code in (200, 201):
                        accepted += 1
                    else:
                        last_err = f"{r.status_code} {r.text[:120]}"
                if accepted > 0:
                    out["logs"] += accepted
                elif last_err:
                    out["errors"].append(
                        f"{et} batch {i // batch_size}: {last_err}"
                    )

    out["total_errors"] = len(out["errors"])
    return out


# ---------------------------------------------------------------------------
# Direct DB mode
# ---------------------------------------------------------------------------


def import_direct(verbose: bool = True) -> dict:
    """Insert directly via the backend's DB helpers (skips HTTP stack)."""
    from src.backend.app.db.session import get_connection, initialize_database, utc_now

    initialize_database()
    out: dict[str, Any] = {"users": 0, "devices": 0, "logs": 0, "errors": []}

    with get_connection() as conn:
        # Users
        for u in _load_users():
            now = utc_now()
            try:
                conn.execute(
                    """
                    INSERT INTO users (
                        id, username, full_name, email, department, job_role, status,
                        risk_score, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'active', 0, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        email = EXCLUDED.email,
                        department = EXCLUDED.department,
                        job_role = EXCLUDED.job_role,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (u["id"], u["username"], u["full_name"], u["email"],
                     u["department"], u["job_role"], now, now),
                )
                out["users"] += 1
            except Exception as exc:  # noqa: BLE001
                out["errors"].append(f"user {u['id']}: {exc}")

        # Devices
        for d in _load_devices():
            now = utc_now()
            try:
                conn.execute(
                    """
                    INSERT INTO devices (
                        id, hostname, os, ip_address, assigned_user_id, status,
                        risk_score, last_seen, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, 'online', 0, %s, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        hostname = EXCLUDED.hostname,
                        os = EXCLUDED.os,
                        ip_address = EXCLUDED.ip_address,
                        assigned_user_id = EXCLUDED.assigned_user_id,
                        last_seen = EXCLUDED.last_seen,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (d["id"], d["hostname"], d["os"], d["ip_address"],
                     d["assigned_user_id"], now, now, now),
                )
                out["devices"] += 1
            except Exception as exc:  # noqa: BLE001
                out["errors"].append(f"device {d['id']}: {exc}")

        # Events
        for et in ("logon", "device", "file", "http", "email"):
            events = _events_for(et)
            now = utc_now()
            ok = 0
            for ev in events:
                try:
                    conn.execute(
                        """
                        INSERT INTO event_logs (
                            source_id, source_file, timestamp, user_id, device_id,
                            event_type, action, resource, metadata_json, raw_json,
                            created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(source_id) DO UPDATE SET
                            timestamp = EXCLUDED.timestamp,
                            metadata_json = EXCLUDED.metadata_json,
                            raw_json = EXCLUDED.raw_json
                        """,
                        (
                            ev["source_id"], ev["source_file"], ev["timestamp"],
                            ev["user_id"], ev["device_id"], ev["event_type"],
                            ev["action"], ev["resource"],
                            json.dumps(ev["metadata"], sort_keys=True),
                            json.dumps(ev["raw"], sort_keys=True, default=str),
                            now,
                        ),
                    )
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    out["errors"].append(f"{et}: {exc}")
            out["logs"] += ok
            if verbose:
                print(f"  {et}: {ok}/{len(events)} inserted")

    out["total_errors"] = len(out["errors"])
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Import mock dataset into UEBA backend")
    ap.add_argument("--server-url", default=os.environ.get("AGENT_SERVER_URL",
                                                            "http://localhost:5173"))
    ap.add_argument("--email", default="admin@demo.com")
    ap.add_argument("--password", default="admin123")
    ap.add_argument("--direct", action="store_true",
                    help="Insert directly via psycopg (skip HTTP stack)")
    ap.add_argument("--batch-size", type=int, default=200)
    args = ap.parse_args()

    if not MOCK_DIR.is_dir():
        print(f"ERROR: mock data dir not found: {MOCK_DIR}", file=sys.stderr)
        print("Run first: python scripts/generate_mock_data.py", file=sys.stderr)
        return 2

    print(f"Mock data dir: {MOCK_DIR}")
    print(f"Mode: {'direct DB' if args.direct else 'HTTP API'}")
    if not args.direct:
        print(f"Server: {args.server_url}")
        print(f"Login:  {args.email}")

    if args.direct:
        try:
            result = import_direct(verbose=True)
        except RuntimeError as exc:
            if "psycopg-pool" in str(exc) or "psycopg" in str(exc).lower():
                print(f"\nLỖI: {exc}", file=sys.stderr)
                print("Host không có psycopg-pool. Cách khắc phục:", file=sys.stderr)
                print("  1) Chạy API mode (khuyên dùng):", file=sys.stderr)
                print("     python scripts/import_mock_data.py", file=sys.stderr)
                print("  2) Hoặc import trong Docker:", file=sys.stderr)
                print("     cat scripts/import_mock_data.py | docker compose exec -T app python3 - --direct", file=sys.stderr)
                print("  3) Hoặc cài dependency trên host:", file=sys.stderr)
                print("     pip install -r requirements.txt", file=sys.stderr)
                return 1
            raise
    else:
        result = import_via_api(
            server_url=args.server_url,
            email=args.email,
            password=args.password,
            batch_size=args.batch_size,
            verbose=True,
        )

    print()
    print("=" * 50)
    total_users = result.get("users", 0) + result.get("users_existed", 0)
    total_devices = result.get("devices", 0) + result.get("devices_existed", 0)
    print(f"Users:   {total_users} ({result.get('users', 0)} mới, {result.get('users_existed', 0)} đã có)")
    print(f"Devices: {total_devices} ({result.get('devices', 0)} mới, {result.get('devices_existed', 0)} đã có)")
    print(f"Logs:    {result['logs']}")
    print(f"Errors:  {result['total_errors']}")
    if result["errors"]:
        print("\nFirst 5 errors:")
        for e in result["errors"][:5]:
            print(f"  - {e}")
    return 0 if result["total_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
