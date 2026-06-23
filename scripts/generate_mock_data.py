"""Generate a small, realistic mock CERT-style dataset for manual demo.

Run from the repo root:

    python scripts/generate_mock_data.py

Output: data/mock/*.csv  (and data/mock/LDAP/2010-01.csv)

The dataset contains 8 users across 4 departments, 5 days of activity, with
roughly 75% normal behavior and 25% deliberately anomalous events that the
UEBA pipeline should flag (late-night logon, blocked URL, USB + .exe file
copy, large external email with attachment). The 8 user IDs are deterministic
and short so they fit the front-end search box easily.

This is intentionally NOT a real CERT dump — values are synthesized and the
"anomalies" are designed to be obvious to a human reviewer reading the CSVs.
The sample/ dataset keeps the original small CERT sample for full pipeline
fidelity; this mock/ is for demos where you want named users and visible
anomalies in 1-2 lines of CSV.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"
LDAP_DIR = OUTPUT_DIR / "LDAP"

USERS = [
    # (user_id, full_name, role, dept, team, supervisor, email)
    ("NGF0157", "Alice Carter",  "Accountant",     "Finance",      "Tax",         "Dean Hines",       "alice.carter@demo.corp"),
    ("LRR0148", "Bob Reyes",     "Engineer",       "Engineering", "Backend",     "Maya Lin",          "bob.reyes@demo.corp"),
    ("MOH0273", "Carol Nguyen",  "Engineer",       "Engineering", "Frontend",    "Maya Lin",          "carol.nguyen@demo.corp"),
    ("LAP0338", "David Park",    "Analyst",        "Operations",   "BI",          "Hana Suzuki",       "david.park@demo.corp"),
    ("BTR0002", "Eva Thompson",  "Specialist",     "HR",           "Recruiting",  "Hana Suzuki",       "eva.thompson@demo.corp"),
    ("ACM0001", "Frank Mendez",  "Manager",        "Sales",        "EMEA",        "VP Sales",          "frank.mendez@demo.corp"),
    ("CNL0003", "Grace Liu",     "Auditor",        "Legal",        "Compliance",  "General Counsel",   "grace.liu@demo.corp"),
    ("ADM0099", "Henry Adams",   "Operator",       "Operations",   "IT Ops",      "Hana Suzuki",       "henry.adams@demo.corp"),
]

DEVICES = [
    # (pc_id, hostname, os, ip)
    ("PC-6056", "WS-ALICE-01",   "Windows 11", "10.20.10.15"),
    ("PC-4275", "WS-BOB-02",     "Ubuntu 22",  "10.20.10.16"),
    ("PC-6699", "WS-CAROL-03",   "macOS 14",   "10.20.10.17"),
    ("PC-5758", "WS-DAVID-04",   "Windows 11", "10.20.10.18"),
    ("PC-7811", "WS-EVA-05",     "Ubuntu 22",  "10.20.10.19"),
]

# Map user -> primary device (1 user may have multiple for realism).
USER_DEVICE = {
    "NGF0157": "PC-6056",
    "LRR0148": "PC-4275",
    "MOH0273": "PC-6699",
    "LAP0338": "PC-5758",
    "BTR0002": "PC-6056",  # shares WS-ALICE-01 with Alice (hot-desking)
    "ACM0001": "PC-4275",  # shares with Bob
    "CNL0003": "PC-5758",  # shares with David
    "ADM0099": "PC-7811",
}

DEPARTMENTS = {u[0]: u[3] for u in USERS}

# Simulate 5 working days starting 2026-06-15 (Monday).
START_DAY = datetime(2026, 6, 15, 0, 0, 0)
WORK_DAYS = 5

# Anomaly profile per user. Each entry is (event_type, fraction, generator).
# Generator returns a dict matching the CERT row format for that type.
ANOMALY_PROFILES: dict[str, list[tuple[str, float, callable]]] = {
    # Bob (LRR0148) — late-night logon + blocked URL (wikileaks/pastebin)
    "LRR0148": [
        ("logon", 0.10, lambda uid, ts, pc: {
            "id": _id(),
            "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
            "user": uid, "pc": pc, "activity": "Logon",
        }),
        ("http", 0.40, lambda uid, ts, pc: {
            "id": _id(),
            "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
            "user": uid, "pc": pc,
            "url": random.choice([
                "http://wikileaks.org/cables/2026/06.html",
                "https://pastebin.com/raw/abc123",
                "https://mega.nz/file/secret#key",
            ]),
            "content": "sensitive data exfil target",
        }),
    ],
    # Carol (MOH0273) — USB device with .exe + copy to removable
    "MOH0273": [
        ("device", 0.30, lambda uid, ts, pc: {
            "id": _id(),
            "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
            "user": uid, "pc": pc, "activity": "Connect",
        }),
        ("file", 0.50, lambda uid, ts, pc: {
            "id": _id(),
            "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
            "user": uid, "pc": pc,
            "filename": random.choice([
                "C-Drive/Projects/payroll_dump.exe",
                "Documents/confidential_Q3.zip",
                "bin/keylogger.exe",
            ]),
            "content": "executable on removable media",
        }),
    ],
    # David (LAP0338) — large external email with attachment
    "LAP0338": [
        ("email", 0.30, lambda uid, ts, pc: {
            "id": _id(),
            "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
            "user": uid, "pc": pc,
            "to": random.choice([
                "personal@gmail.com",
                "competitor@external.io",
                "drop@protonmail.com",
            ]),
            "cc": "",
            "bcc": "",
            "from": "david.park@demo.corp",
            "size": random.choice([8500000, 15000000, 25000000]),
            "attachments": random.choice([2, 5, 12]),
            "content": "sensitive business data leak",
        }),
    ],
    # Frank (ACM0001) — high-risk after-hours logon
    "ACM0001": [
        ("logon", 0.20, lambda uid, ts, pc: {
            "id": _id(),
            "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
            "user": uid, "pc": pc, "activity": "Logon",
        }),
    ],
}


def _id() -> str:
    """Generate a CERT-style brace id."""
    return "{" + uuid.uuid4().hex.upper()[:24] + "}"


def _ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LDAP_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# LDAP (single snapshot file)
# ---------------------------------------------------------------------------


def write_ldap() -> None:
    out = LDAP_DIR / "2010-01.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "employee_name", "user_id", "email", "role",
            "business_unit", "functional_unit", "department", "team", "supervisor",
        ])
        for uid, name, role, dept, team, supervisor, email in USERS:
            w.writerow([name, uid, email, role, "1",
                        f"{dept} Team", dept, team, supervisor])
    print(f"  Wrote {out} ({len(USERS)} employees)")


# ---------------------------------------------------------------------------
# Psychometric
# ---------------------------------------------------------------------------


def write_psychometric() -> None:
    out = OUTPUT_DIR / "psychometric.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["employee_name", "user_id", "O", "C", "E", "A", "N"])
        for uid, name, *_ in USERS:
            # Big-Five scores roughly in 30-70 range, varied per user.
            w.writerow([name, uid,
                        random.randint(35, 70),  # O openness
                        random.randint(35, 70),  # C conscientiousness
                        random.randint(30, 70),  # E extraversion
                        random.randint(35, 70),  # A agreeableness
                        random.randint(30, 65)])  # N neuroticism
    print(f"  Wrote {out} ({len(USERS)} profiles)")


# ---------------------------------------------------------------------------
# Event generators
# ---------------------------------------------------------------------------


def gen_logon_normal(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc, "activity": "Logon",
    }


def gen_logon_after_hours(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc, "activity": "Logon",
    }


def gen_logoff(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc, "activity": "Logoff",
    }


def gen_http_normal(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc,
        "url": random.choice([
            "https://news.ycombinator.com/",
            "https://stackoverflow.com/questions/12345",
            "https://docs.python.org/3/library/csv.html",
            "https://github.com/company/internal-tool",
            "https://www.bing.com/search?q=hello",
        ]),
        "content": "normal browsing activity",
    }


def gen_http_blocked(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc,
        "url": random.choice([
            "http://wikileaks.org/cables/2026/06.html",
            "https://pastebin.com/raw/xyz789",
            "https://mega.nz/file/secret#key",
        ]),
        "content": "blocked site visit",
    }


def gen_file_normal(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc,
        "filename": random.choice([
            f"Documents/report_{ts.day}.docx",
            "Projects/spec.md",
            f"Downloads/photo_{ts.day}.jpg",
            f"Notes/notes_{ts.day}.txt",
        ]),
        "content": "normal file access",
    }


def gen_file_exe(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc,
        "filename": random.choice([
            "C-Drive/Projects/payroll_dump.exe",
            "Documents/confidential_Q3.zip",
            "bin/keylogger.exe",
            "Downloads/payload.exe",
        ]),
        "content": "executable on endpoint",
    }


def gen_email_normal(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc,
        "to": random.choice([
            "colleague@demo.corp", "manager@demo.corp",
            "team@demo.corp", "support@demo.corp",
        ]),
        "cc": "", "bcc": "", "from": f"{uid}@demo.corp",
        "size": random.randint(2000, 50000),
        "attachments": random.randint(0, 1),
        "content": "normal email",
    }


def gen_email_external(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc,
        "to": random.choice([
            "personal@gmail.com",
            "competitor@external.io",
            "drop@protonmail.com",
        ]),
        "cc": "", "bcc": "", "from": f"{uid}@demo.corp",
        "size": random.choice([8_000_000, 15_000_000, 25_000_000]),
        "attachments": random.choice([2, 5, 12]),
        "content": "sensitive business data leak",
    }


def gen_device_normal(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc,
        "activity": random.choice(["Connect", "Disconnect"]),
    }


def gen_device_suspicious(uid: str, ts: datetime, pc: str) -> dict:
    return {
        "id": _id(),
        "date": ts.strftime("%m/%d/%Y %H:%M:%S"),
        "user": uid, "pc": pc, "activity": "Connect",
    }


# Per-day, per-user target counts of normal activity.
NORMAL_COUNTS = {
    "logon": 4,    # 2 logon + 2 logoff per day
    "logoff": 0,   # merged into logon (alternating)
    "http": 12,
    "file": 6,
    "email": 4,
    "device": 2,
}


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


def work_minutes_for_hour(h: int) -> int:
    """Working hours: 8-12 morning, 13-17 afternoon. Density peaks 9-11 / 14-16."""
    if h in (9, 10, 11, 14, 15, 16):
        return 8
    if h in (8, 12, 13, 17):
        return 4
    return 0  # off-hours (rare random ticks possible)


def should_emit_after_hours() -> bool:
    return random.random() < 0.05  # 5% of events land after hours


def random_work_ts(day: datetime) -> datetime:
    """Pick a random timestamp in a work hour, or rarely after hours."""
    if should_emit_after_hours():
        h = random.choice(list(range(0, 24)))
    else:
        # Weighted hour selection.
        hours_pool = []
        for h in range(24):
            for _ in range(work_minutes_for_hour(h)):
                hours_pool.append(h)
        if not hours_pool:
            h = 9
        else:
            h = random.choice(hours_pool)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return day.replace(hour=h, minute=m, second=s)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    global OUTPUT_DIR, LDAP_DIR
    ap = argparse.ArgumentParser(
        description="Generate synthetic CERT-style mock dataset for manual demo"
    )
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for reproducible datasets (default: 42)")
    ap.add_argument("--out", type=Path, default=OUTPUT_DIR,
                    help="Output directory (default: data/mock)")
    args = ap.parse_args(argv)

    random.seed(args.seed)
    # Allow overriding the output dir for tests.
    OUTPUT_DIR = args.out
    LDAP_DIR = OUTPUT_DIR / "LDAP"
    _ensure_dirs()

    # Buckets per event type.
    logon_rows: list[dict] = []
    http_rows: list[dict] = []
    file_rows: list[dict] = []
    email_rows: list[dict] = []
    device_rows: list[dict] = []

    for day_offset in range(WORK_DAYS):
        day = START_DAY + timedelta(days=day_offset)
        for uid, *_ in USERS:
            pc = USER_DEVICE[uid]
            # Normal: logon + logoff alternating.
            normal_logon_count = NORMAL_COUNTS["logon"]
            for i in range(normal_logon_count):
                ts = random_work_ts(day)
                if i % 2 == 0:
                    logon_rows.append(gen_logon_normal(uid, ts, pc))
                else:
                    logon_rows.append(gen_logoff(uid, ts, pc))

            # Normal http.
            for _ in range(NORMAL_COUNTS["http"]):
                http_rows.append(gen_http_normal(uid, random_work_ts(day), pc))

            # Normal file.
            for _ in range(NORMAL_COUNTS["file"]):
                file_rows.append(gen_file_normal(uid, random_work_ts(day), pc))

            # Normal email.
            for _ in range(NORMAL_COUNTS["email"]):
                email_rows.append(gen_email_normal(uid, random_work_ts(day), pc))

            # Normal device (mostly disconnect).
            for _ in range(NORMAL_COUNTS["device"]):
                device_rows.append(gen_device_normal(uid, random_work_ts(day), pc))

            # Anomalies: vary by user.
            profiles = ANOMALY_PROFILES.get(uid, [])
            for et, fraction, gen in profiles:
                if random.random() < fraction:
                    ts = random_work_ts(day)
                    if et == "logon":
                        logon_rows.append(gen(uid, ts, pc))
                    elif et == "http":
                        http_rows.append({
                            **gen(uid, ts, pc),
                            "url": random.choice([
                                "http://wikileaks.org/cables/2026/06.html",
                                "https://pastebin.com/raw/xyz789",
                                "https://mega.nz/file/secret#key",
                            ]),
                            "content": "blocked site visit",
                        })
                    elif et == "file":
                        file_rows.append({
                            **gen(uid, ts, pc),
                            "filename": random.choice([
                                "C-Drive/Projects/payroll_dump.exe",
                                "Documents/confidential_Q3.zip",
                                "bin/keylogger.exe",
                                "Downloads/payload.exe",
                            ]),
                            "content": "executable on removable media",
                        })
                    elif et == "email":
                        email_rows.append({
                            **gen(uid, ts, pc),
                            "to": random.choice([
                                "personal@gmail.com",
                                "competitor@external.io",
                                "drop@protonmail.com",
                            ]),
                            "size": random.choice([8_000_000, 15_000_000, 25_000_000]),
                            "attachments": random.choice([2, 5, 12]),
                            "content": "sensitive business data leak",
                        })
                    elif et == "device":
                        device_rows.append(gen(uid, ts, pc))

    # Write CSVs.
    def _write(name: str, rows: list[dict]) -> None:
        if not rows:
            return
        out = OUTPUT_DIR / f"{name}.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"  Wrote {out} ({len(rows)} rows)")

    _write("logon", logon_rows)
    _write("http", http_rows)
    _write("file", file_rows)
    _write("email", email_rows)
    _write("device", device_rows)

    write_ldap()
    write_psychometric()

    print(f"\nDone. 5 days, {len(USERS)} users. Total events: "
          f"{len(logon_rows) + len(http_rows) + len(file_rows) + len(email_rows) + len(device_rows)}")


if __name__ == "__main__":
    sys.exit(main() or 0)
