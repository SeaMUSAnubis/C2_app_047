"""Generate a small, realistic mock CERT-style dataset for manual demo.

Run from the repo root:

    python scripts/generate_mock_data.py

Output: data/mock/*.csv  (and data/mock/LDAP/2010-01.csv)

The dataset contains 8 users across 4 departments, 5 days of activity, with
roughly 60-65% normal behavior and 35-40% deliberately anomalous events that
the UEBA pipeline should flag.  ALL 8 users have distinct anomaly patterns so
every filter and dashboard view shows interesting data.

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
    ("PC-9991", "WS-HENRY-06",   "Windows 10", "10.20.10.20"),
    ("PC-8882", "WS-FRANK-07",   "macOS 13",   "10.20.10.21"),
    ("PC-7773", "WS-GRACE-08",   "Windows 11", "10.20.10.22"),
]

# Map user -> primary device
USER_DEVICE = {
    "NGF0157": "PC-6056",
    "LRR0148": "PC-4275",
    "MOH0273": "PC-6699",
    "LAP0338": "PC-5758",
    "BTR0002": "PC-6056",  # shares with Alice (hot-desking)
    "ACM0001": "PC-8882",
    "CNL0003": "PC-7773",
    "ADM0099": "PC-9991",
}
# Secondary devices some users also use (lateral movement)
USER_SECONDARY = {
    "ADM0099": "PC-7811",   # Henry uses Eva's machine sometimes
    "LRR0148": "PC-7773",   # Bob uses Grace's machine
    "MOH0273": "PC-4275",   # Carol uses Bob's machine
}

DEPARTMENTS = {u[0]: u[3] for u in USERS}

# Simulate 5 working days starting 2026-06-15 (Monday).
START_DAY = datetime(2026, 6, 15, 0, 0, 0)
WORK_DAYS = 5

# ═══════════════════════════════════════════════════════════════════════════════
# Suspicious payload pools
# ═══════════════════════════════════════════════════════════════════════════════

MALICIOUS_URLS = [
    "http://wikileaks.org/cables/2026/06.html",
    "https://pastebin.com/raw/abc123",
    "https://mega.nz/file/secret#key",
    "http://darknet-market.onion/vendor/cc-dumps",
    "https://c2-server.xyz/beacon.php",
    "http://phishing-login.com/office365/auth",
    "https://malware-cdn.net/dropper.exe",
    "http://ransomware-panel.onion/admin",
    "https://exfil-storage.ru/upload/archive",
    "http://tor2web-proxy.link/access",
    "https://cryptominer-pool.io/miner.js",
    "http://0day-exploit.ru/shell",
]

EXFIL_EMAILS = [
    "personal@gmail.com",
    "competitor@external.io",
    "drop@protonmail.com",
    "hacker@riseup.net",
    "anon@tutanota.com",
    "whistleblower@protonmail.ch",
    "darkbuyer@torbox.net",
    "shadowbroker@mail2tor.com",
]

SUSPICIOUS_FILES = [
    "C-Drive/Projects/payroll_dump.exe",
    "Documents/confidential_Q3.zip",
    "bin/keylogger.exe",
    "Downloads/payload.exe",
    "C-Drive/Windows/System32/mimikatz.exe",
    "Temp/ransomware_encryptor.bin",
    "AppData/Local/cobalt_strike.dll",
    "Documents/financial_records_2026.xlsx.encrypted",
    "Projects/source_code_backup.tar.gz",
    "Downloads/cracked-software.exe",
    "C-Drive/Tools/nmap_port_scanner.exe",
    "Temp/wscript_macro.docm",
]

SUSPICIOUS_IPS = [
    "185.220.101.34",
    "45.33.32.156",
    "198.51.100.23",
    "203.0.113.99",
    "91.121.87.44",
    "5.255.88.99",
    "176.9.45.1",
    "138.197.44.2",
]

# ═══════════════════════════════════════════════════════════════════════════════
# Anomaly profiles — EVERY user has at least 2 anomaly types
# ═══════════════════════════════════════════════════════════════════════════════

# Fraction per day: each user has ~35-40% chance of generating an anomaly
# of each type they're assigned.  With 6 anomaly types, about half the
# generated events will be anomalous.

ANOMALY_PROFILES: dict[str, list[tuple[str, float, str]]] = {
    # ── Alice (NGF0157) — data exfiltration + blocked sites ──
    "NGF0157": [
        ("email_exfil", 0.70, "Gửi email chứa file nhạy cảm ra bên ngoài"),
        ("http_blocked", 0.60, "Truy cập trang web bị chặn / độc hại"),
        ("file_exe", 0.50, "Truy cập file .exe đáng ngờ"),
    ],
    # ── Bob (LRR0148) — late-night + wikileaks heavy ──
    "LRR0148": [
        ("logon_after_hours", 0.80, "Đăng nhập ngoài giờ làm việc (0h-5h sáng)"),
        ("http_blocked", 0.70, "Truy cập Wikileaks / Pastebin"),
        ("device_usb", 0.40, "Cắm thiết bị USB lạ"),
    ],
    # ── Carol (MOH0273) — USB + .exe heavy ──
    "MOH0273": [
        ("device_usb", 0.80, "Kết nối thiết bị USB không rõ nguồn gốc"),
        ("file_exe", 0.70, "Chạy file thực thi từ USB"),
        ("network_suspicious", 0.50, "Kết nối đến IP đáng ngờ"),
    ],
    # ── David (LAP0338) — email leak + after-hours ──
    "LAP0338": [
        ("email_exfil", 0.70, "Gửi email dung lượng lớn ra ngoài"),
        ("logon_after_hours", 0.60, "Đăng nhập lúc nửa đêm"),
        ("file_mass_download", 0.50, "Tải hàng loạt file nội bộ"),
    ],
    # ── Eva (BTR0002) — lateral movement + HR data access ──
    "BTR0002": [
        ("logon_other_device", 0.60, "Đăng nhập từ thiết bị của người khác"),
        ("file_sensitive", 0.70, "Truy cập file nhân sự nhạy cảm"),
        ("email_exfil", 0.50, "Gửi dữ liệu HR ra ngoài"),
    ],
    # ── Frank (ACM0001) — sales data theft + after-hours ──
    "ACM0001": [
        ("logon_after_hours", 0.70, "Đăng nhập cuối tuần / ban đêm"),
        ("file_mass_download", 0.60, "Tải toàn bộ danh sách khách hàng"),
        ("http_blocked", 0.50, "Truy cập darknet / proxy ẩn danh"),
    ],
    # ── Grace (CNL0003) — privilege escalation + compliance bypass ──
    "CNL0003": [
        ("file_sensitive", 0.70, "Truy cập file pháp lý không được phép"),
        ("logon_other_device", 0.55, "Đăng nhập từ máy khác"),
        ("network_suspicious", 0.45, "Kết nối ra IP nước ngoài lạ"),
    ],
    # ── Henry (ADM0099) — insider threat: IT Ops abuse ──
    "ADM0099": [
        ("logon_other_device", 0.65, "Đăng nhập vào máy người khác (quyền IT)"),
        ("device_usb", 0.60, "Cắm USB lạ vào server"),
        ("file_exe", 0.55, "Chạy tool quét mạng / crack mật khẩu"),
        ("network_suspicious", 0.50, "Kết nối ra C2 server"),
    ],
}


def _id() -> str:
    """Generate a CERT-style brace id."""
    return "{" + uuid.uuid4().hex.upper()[:24] + "}"


def _ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LDAP_DIR.mkdir(parents=True, exist_ok=True)


def _after_hours_ts(day: datetime, hour_range: tuple[int, int] = (0, 5)) -> datetime:
    """Generate a timestamp in the dead-of-night range."""
    h = random.randint(*hour_range)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return day.replace(hour=h, minute=m, second=s)


def _fmt_ts(ts: datetime) -> str:
    return ts.strftime("%m/%d/%Y %H:%M:%S")


# ---------------------------------------------------------------------------
# LDAP
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
            w.writerow([name, uid,
                        random.randint(35, 70),
                        random.randint(35, 70),
                        random.randint(30, 70),
                        random.randint(35, 70),
                        random.randint(30, 65)])
    print(f"  Wrote {out} ({len(USERS)} profiles)")


# ---------------------------------------------------------------------------
# Normal event generators
# ---------------------------------------------------------------------------

def gen_logon_normal(uid: str, ts: datetime, pc: str) -> dict:
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc, "activity": "Logon"}

def gen_logoff(uid: str, ts: datetime, pc: str) -> dict:
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc, "activity": "Logoff"}

def gen_http_normal(uid: str, ts: datetime, pc: str) -> dict:
    urls = [
        "https://news.ycombinator.com/",
        "https://stackoverflow.com/questions/12345",
        "https://docs.python.org/3/library/csv.html",
        "https://github.com/company/internal-tool",
        "https://www.bing.com/search?q=hello",
        "https://confluence.internal.corp/pages/hr-policy",
        "https://jira.internal.corp/browse/DEV-421",
        "https://slack.com/team/engineering",
        "https://mail.google.com/",
        "https://calendar.google.com/",
        "https://teams.microsoft.com/",
        "https://dashboard.internal.corp/metrics",
    ]
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "url": random.choice(urls), "content": "normal browsing activity"}

def gen_file_normal(uid: str, ts: datetime, pc: str) -> dict:
    files = [
        f"Documents/report_{ts.day}.docx",
        "Projects/spec.md",
        f"Downloads/photo_{ts.day}.jpg",
        f"Notes/notes_{ts.day}.txt",
        "Documents/meeting_minutes.pdf",
        "Projects/sprint_backlog.xlsx",
        "Downloads/invoice_template.docx",
        "Documents/presentation_q3.pptx",
    ]
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "filename": random.choice(files), "content": "normal file access"}

def gen_email_normal(uid: str, ts: datetime, pc: str) -> dict:
    to = random.choice(["colleague@demo.corp", "manager@demo.corp",
                         "team@demo.corp", "support@demo.corp"])
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "to": to, "cc": "", "bcc": "", "from": f"{uid}@demo.corp",
            "size": random.randint(2000, 50000),
            "attachments": random.randint(0, 1),
            "content": "normal email"}

def gen_device_normal(uid: str, ts: datetime, pc: str) -> dict:
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "activity": random.choice(["Connect", "Disconnect"])}


# ---------------------------------------------------------------------------
# Anomaly event generators — one function per anomaly type
# ---------------------------------------------------------------------------

def gen_logon_after_hours_anomaly(uid: str, day: datetime, pc: str) -> dict:
    ts = _after_hours_ts(day, (0, 5))
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc, "activity": "Logon"}

def gen_http_blocked_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "url": random.choice(MALICIOUS_URLS),
            "content": "blocked / malicious site visit"}

def gen_email_exfil_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "to": random.choice(EXFIL_EMAILS),
            "cc": "", "bcc": "",
            "from": f"{uid}@demo.corp",
            "size": random.choice([8_500_000, 15_000_000, 25_000_000, 40_000_000, 75_000_000]),
            "attachments": random.choice([2, 5, 8, 12, 20]),
            "content": "sensitive business data exfiltration"}

def gen_file_exe_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "filename": random.choice(SUSPICIOUS_FILES),
            "content": "suspicious executable / script access"}

def gen_device_usb_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc, "activity": "Connect"}

def gen_network_suspicious_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    ip = random.choice(SUSPICIOUS_IPS)
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "url": f"https://{ip}:8443/admin",
            "content": f"connection to suspicious IP {ip}"}

def gen_logon_other_device_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    """Logon from a device that isn't the user's primary."""
    # Pick a device that belongs to someone else
    other_pc = random.choice([d[0] for d in DEVICES if d[0] != USER_DEVICE.get(uid)])
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": other_pc, "activity": "Logon"}

def gen_file_sensitive_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    sensitive = [
        "HR/salaries_2026.xlsx",
        "Finance/budget_confidential.pdf",
        "Legal/merger_documents.docx",
        "HR/employee_reviews_2026.pdf",
        "Finance/tax_evasion_plan.xlsx",
        "Legal/lawsuit_settlement.docx",
        "HR/disciplinary_records.pdf",
        "Legal/patent_filing_confidential.docx",
    ]
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "filename": random.choice(sensitive),
            "content": "access to sensitive/restricted file"}

def gen_file_mass_download_anomaly(uid: str, ts: datetime, pc: str) -> dict:
    mass_files = [
        "Downloads/customer_list_full.csv",
        "Downloads/source_code_dump.tar.gz",
        "Downloads/all_employee_data.xlsx",
        "Downloads/database_backup.sql.gz",
        "Downloads/project_archive_complete.zip",
    ]
    return {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": pc,
            "filename": random.choice(mass_files),
            "content": "mass data download / archive access"}

# Map anomaly codes → (generator_func, event_type)
ANOMALY_GENERATORS: dict[str, tuple[callable, str]] = {
    "logon_after_hours": (gen_logon_after_hours_anomaly, "logon"),
    "http_blocked": (gen_http_blocked_anomaly, "http"),
    "email_exfil": (gen_email_exfil_anomaly, "email"),
    "file_exe": (gen_file_exe_anomaly, "file"),
    "device_usb": (gen_device_usb_anomaly, "device"),
    "network_suspicious": (gen_network_suspicious_anomaly, "http"),
    "logon_other_device": (gen_logon_other_device_anomaly, "logon"),
    "file_sensitive": (gen_file_sensitive_anomaly, "file"),
    "file_mass_download": (gen_file_mass_download_anomaly, "file"),
}

# Per-day, per-user target counts of normal activity.
NORMAL_COUNTS = {
    "logon": 3,    # reduced so anomalies stand out proportionally
    "http": 6,
    "file": 3,
    "email": 2,
    "device": 1,
}


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def work_minutes_for_hour(h: int) -> int:
    """Working hours: 8-12 morning, 13-17 afternoon. Density peaks 9-11 / 14-16."""
    if h in (9, 10, 11, 14, 15, 16):
        return 8
    if h in (8, 12, 13, 17):
        return 4
    if h in (18, 19):
        return 2  # some overtime
    return 0

def random_work_ts(day: datetime, after_hours_pct: float = 0.05) -> datetime:
    """Pick a random timestamp, mostly during work hours."""
    if random.random() < after_hours_pct:
        h = random.choice(list(range(0, 24)))
    else:
        hours_pool = [h for h in range(24) for _ in range(work_minutes_for_hour(h))]
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
    ap.add_argument("--days", type=int, default=WORK_DAYS,
                    help=f"Number of work days to simulate (default: {WORK_DAYS})")
    ap.add_argument("--out", type=Path, default=OUTPUT_DIR,
                    help="Output directory (default: data/mock)")
    args = ap.parse_args(argv)

    random.seed(args.seed)
    OUTPUT_DIR = args.out
    LDAP_DIR = OUTPUT_DIR / "LDAP"
    _ensure_dirs()

    # Buckets per event type.
    logon_rows: list[dict] = []
    http_rows: list[dict] = []
    file_rows: list[dict] = []
    email_rows: list[dict] = []
    device_rows: list[dict] = []

    # Dedup tracker.
    _seen: set[tuple[str, str, str, str, str]] = set()

    def _dedup_key(row: dict, event_type: str) -> tuple[str, str, str, str, str]:
        return (
            row["user"],
            row["pc"],
            event_type,
            row.get("url", row.get("filename", row.get("to", row.get("activity", "")))),
            row["date"],
        )

    def _is_dup(row: dict, event_type: str) -> bool:
        key = _dedup_key(row, event_type)
        if key in _seen:
            return True
        _seen.add(key)
        return False

    anomaly_stats: dict[str, int] = {}
    normal_stats: dict[str, int] = {}

    for day_offset in range(args.days):
        day = START_DAY + timedelta(days=day_offset)
        for uid, *_ in USERS:
            pc = USER_DEVICE[uid]

            # ── ANOMALIES FIRST (win dedup race) ──
            profiles = ANOMALY_PROFILES.get(uid, [])
            for anomaly_code, fraction, desc in profiles:
                # fire 1-3 anomaly events per type per day
                count = 1
                if random.random() < fraction:
                    count = 2
                if random.random() < fraction * 0.6:
                    count = 3
                for _ in range(count):
                    gen_func, event_type = ANOMALY_GENERATORS[anomaly_code]
                    ts = random_work_ts(day, after_hours_pct=0.40)
                    row = gen_func(uid, ts, pc)
                    if not _is_dup(row, event_type):
                        if event_type == "logon":
                            logon_rows.append(row)
                        elif event_type == "http":
                            http_rows.append(row)
                        elif event_type == "file":
                            file_rows.append(row)
                        elif event_type == "email":
                            email_rows.append(row)
                        elif event_type == "device":
                            device_rows.append(row)
                        anomaly_stats[desc] = anomaly_stats.get(desc, 0) + 1

            # Secondary-device lateral movement
            sec_pc = USER_SECONDARY.get(uid)
            if sec_pc and random.random() < 0.50:
                ts = random_work_ts(day, after_hours_pct=0.40)
                row = {"id": _id(), "date": _fmt_ts(ts), "user": uid, "pc": sec_pc, "activity": "Logon"}
                if not _is_dup(row, "logon"):
                    logon_rows.append(row)
                    anomaly_stats["Đăng nhập từ thiết bị phụ (lateral movement)"] = \
                        anomaly_stats.get("Đăng nhập từ thiết bị phụ (lateral movement)", 0) + 1

            # ── Normal events (after anomalies — get dedup'd if collision) ──
            for i in range(NORMAL_COUNTS["logon"]):
                ts = random_work_ts(day)
                if i % 2 == 0:
                    row = gen_logon_normal(uid, ts, pc)
                    if not _is_dup(row, "logon"):
                        logon_rows.append(row)
                        normal_stats["logon"] = normal_stats.get("logon", 0) + 1
                else:
                    row = gen_logoff(uid, ts, pc)
                    if not _is_dup(row, "logon"):
                        logon_rows.append(row)
                        normal_stats["logoff"] = normal_stats.get("logoff", 0) + 1

            for _ in range(NORMAL_COUNTS["http"]):
                row = gen_http_normal(uid, random_work_ts(day), pc)
                if not _is_dup(row, "http"):
                    http_rows.append(row)
                    normal_stats["http"] = normal_stats.get("http", 0) + 1

            for _ in range(NORMAL_COUNTS["file"]):
                row = gen_file_normal(uid, random_work_ts(day), pc)
                if not _is_dup(row, "file"):
                    file_rows.append(row)
                    normal_stats["file"] = normal_stats.get("file", 0) + 1

            for _ in range(NORMAL_COUNTS["email"]):
                row = gen_email_normal(uid, random_work_ts(day), pc)
                if not _is_dup(row, "email"):
                    email_rows.append(row)
                    normal_stats["email"] = normal_stats.get("email", 0) + 1

            for _ in range(NORMAL_COUNTS["device"]):
                row = gen_device_normal(uid, random_work_ts(day), pc)
                if not _is_dup(row, "device"):
                    device_rows.append(row)
                    normal_stats["device"] = normal_stats.get("device", 0) + 1

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

    total = len(logon_rows) + len(http_rows) + len(file_rows) + len(email_rows) + len(device_rows)
    total_anomalies = sum(anomaly_stats.values())
    print(f"\nDone. {args.days} days, {len(USERS)} users.")
    print(f"Total events:    {total}")
    print(f"Normal events:   {total - total_anomalies}")
    print(f"Anomalous events: {total_anomalies} ({total_anomalies * 100 // max(total, 1)}%)")

    print("\nAnomaly breakdown:")
    for desc, count in sorted(anomaly_stats.items(), key=lambda x: -x[1]):
        print(f"  {count:>4}  {desc}")


if __name__ == "__main__":
    sys.exit(main() or 0)
