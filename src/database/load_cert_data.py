#!/usr/bin/env python3
"""Load CERT r4.2 sample data into the database via API."""

import csv
import json
import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000/api"
DATA_DIR = Path("data/sample/cert-r4.2-small")


def get_admin_token(client: httpx.Client) -> str:
    resp = client.post(
        f"{API_BASE}/auth/login",
        json={"email": "admin@demo.com", "password": "admin123"},
    )
    resp.raise_for_status()
    return resp.json()["accessToken"]


def parse_date(date_str: str) -> str:
    """Convert MM/DD/YYYY HH:MM:SS to ISO 8601."""
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str.strip(), "%m/%d/%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return date_str


def load_users_from_ldap(client: httpx.Client, token: str) -> dict[str, str]:
    """Load users from LDAP data and return user_id -> username mapping."""
    headers = {"Authorization": f"Bearer {token}"}
    ldap_dir = DATA_DIR / "LDAP"
    user_map = {}  # user_id -> username
    created = 0
    
    if not ldap_dir.exists():
        print("LDAP directory not found")
        return user_map
    
    # Read first LDAP file to get users
    ldap_file = sorted(ldap_dir.glob("*.csv"))[0]
    print(f"Loading users from {ldap_file.name}...")
    
    with open(ldap_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        users_seen = set()
        
        for row in reader:
            user_id = row["user_id"]
            if user_id in users_seen:
                continue
            users_seen.add(user_id)
            
            username = user_id.lower()
            full_name = row.get("employee_name", user_id)
            email = row.get("email", "")
            department = row.get("department", "")
            job_role = row.get("role", "")
            
            user_map[user_id] = username
            
            # Create user via API
            resp = client.post(
                f"{API_BASE}/users",
                headers=headers,
                json={
                    "id": user_id,
                    "username": username,
                    "full_name": full_name,
                    "email": email,
                    "department": department,
                    "job_role": job_role,
                    "status": "active",
                    "risk_score": 0,
                },
            )
            
            if resp.status_code in (200, 201):
                created += 1
            elif resp.status_code == 409:
                pass  # Already exists
            else:
                print(f"  Error creating user {user_id}: {resp.status_code} {resp.text[:100]}")
    
    print(f"  Created: {created}, Total in LDAP: {len(user_map)}")
    return user_map


def load_devices_from_logs(client: httpx.Client, token: str, user_map: dict[str, str]) -> dict[str, str]:
    """Create devices from logon.csv data."""
    headers = {"Authorization": f"Bearer {token}"}
    logon_file = DATA_DIR / "logon.csv"
    device_map = {}  # pc_id -> hostname
    created = 0
    
    if not logon_file.exists():
        print("logon.csv not found")
        return device_map
    
    print("Loading devices from logon.csv...")
    
    with open(logon_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        devices_seen = set()
        
        for row in reader:
            pc_id = row["pc"]
            if pc_id in devices_seen:
                continue
            devices_seen.add(pc_id)
            
            # Find assigned user (first user seen with this device)
            assigned_user = row.get("user", "")
            
            device_map[pc_id] = pc_id
            
            resp = client.post(
                f"{API_BASE}/devices",
                headers=headers,
                json={
                    "id": pc_id,
                    "hostname": pc_id,
                    "os": "Windows",
                    "assigned_user_id": assigned_user if assigned_user in user_map else None,
                    "status": "online",
                    "risk_score": 0,
                },
            )
            
            if resp.status_code in (200, 201):
                created += 1
            elif resp.status_code == 409:
                pass
            else:
                print(f"  Error creating device {pc_id}: {resp.status_code} {resp.text[:100]}")
    
    print(f"  Created: {created}, Total devices: {len(device_map)}")
    return device_map


def ingest_logon(row: dict) -> dict:
    activity = row["activity"].lower()
    return {
        "source_id": f"cert-r4.2:logon:{row['id']}",
        "source_file": "logon.csv",
        "timestamp": parse_date(row["date"]),
        "user_id": row["user"],
        "device_id": row["pc"],
        "event_type": "logon",
        "action": activity,
        "resource": row["pc"],
        "metadata": {"activity": activity},
        "raw": row,
    }


def ingest_device(row: dict) -> dict:
    activity = row["activity"].lower()
    return {
        "source_id": f"cert-r4.2:device:{row['id']}",
        "source_file": "device.csv",
        "timestamp": parse_date(row["date"]),
        "user_id": row["user"],
        "device_id": row["pc"],
        "event_type": "device",
        "action": activity,
        "resource": row.get("file", ""),
        "metadata": {"activity": activity},
        "raw": row,
    }


def ingest_file(row: dict) -> dict:
    return {
        "source_id": f"cert-r4.2:file:{row['id']}",
        "source_file": "file.csv",
        "timestamp": parse_date(row["date"]),
        "user_id": row["user"],
        "device_id": row["pc"],
        "event_type": "file",
        "action": row.get("activity", "file_access"),
        "resource": row.get("filename", ""),
        "metadata": {
            "content": row.get("content", ""),
            "to_removable": row.get("to_removable_media", ""),
            "from_removable": row.get("from_removable_media", ""),
        },
        "raw": row,
    }


def ingest_email(row: dict) -> dict:
    return {
        "source_id": f"cert-r4.2:email:{row['id']}",
        "source_file": "email.csv",
        "timestamp": parse_date(row["date"]),
        "user_id": row["user"],
        "device_id": row["pc"],
        "event_type": "email",
        "action": "email_send",
        "resource": row.get("to", ""),
        "metadata": {
            "from": row.get("from", ""),
            "to": row.get("to", ""),
            "cc": row.get("cc", ""),
            "bcc": row.get("bcc", ""),
            "size": row.get("size", ""),
            "attachments": row.get("attachments", ""),
            "content": row.get("content", ""),
        },
        "raw": row,
    }


def ingest_http(row: dict) -> dict:
    return {
        "source_id": f"cert-r4.2:http:{row['id']}",
        "source_file": "http.csv",
        "timestamp": parse_date(row["date"]),
        "user_id": row["user"],
        "device_id": row["pc"],
        "event_type": "http",
        "action": "http_access",
        "resource": row.get("url", ""),
        "metadata": {
            "url": row.get("url", ""),
            "content": row.get("content", ""),
        },
        "raw": row,
    }


INGESTORS = {
    "logon.csv": ingest_logon,
    "device.csv": ingest_device,
    "file.csv": ingest_file,
    "email.csv": ingest_email,
    "http.csv": ingest_http,
}


def load_csv(filepath: Path) -> list[dict]:
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main() -> None:
    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        sys.exit(1)

    with httpx.Client(timeout=30.0) as client:
        print("Getting admin token...")
        token = get_admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Load users from LDAP
        user_map = load_users_from_ldap(client, token)
        
        # Step 2: Create devices
        device_map = load_devices_from_logs(client, token, user_map)

        # Step 3: Ingest events
        total_created = 0
        total_failed = 0

        for filename, ingestor in INGESTORS.items():
            filepath = DATA_DIR / filename
            if not filepath.exists():
                print(f"Skipping {filename} (not found)")
                continue

            rows = load_csv(filepath)
            print(f"\nProcessing {filename}: {len(rows)} rows")

            created = 0
            failed = 0
            
            for row in rows:
                try:
                    event = ingestor(row)
                    resp = client.post(
                        f"{API_BASE}/logs/ingest",
                        headers=headers,
                        json=event,
                    )
                    if resp.status_code in (200, 201):
                        created += 1
                    else:
                        failed += 1
                        if failed <= 3:
                            print(f"  Error: {resp.status_code} - {resp.text[:100]}")
                except Exception as e:
                    failed += 1
                    if failed <= 3:
                        print(f"  Exception: {e}")

            total_created += created
            total_failed += failed
            print(f"  Created: {created}, Failed: {failed}")

        print(f"\n{'='*50}")
        print(f"Users loaded: {len(user_map)}")
        print(f"Devices loaded: {len(device_map)}")
        print(f"Events created: {total_created}")
        print(f"Events failed: {total_failed}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
