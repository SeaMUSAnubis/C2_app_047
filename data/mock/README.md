# Mock Dataset — `data/mock/`

Dataset nhỏ, realistic, có chủ đích cho demo UEBA Endpoint Monitoring. Dùng để người mới test thủ công hệ thống mà không cần dữ liệu thật.

## Tổng quan

| Thông số | Giá trị |
|---|---|
| Số users | 8 (đặt tên theo persona) |
| Số devices | 5 PC (2-3 users share thiết bị kiểu hot-desking) |
| Khoảng thời gian | 5 ngày làm việc (Mon–Fri), bắt đầu `2026-06-15` |
| Tổng events | ~1,130 (logon + device + file + http + email) |
| Tỉ lệ anomaly | ~25% (cố ý để ML/rules phát hiện) |

Users:

| user_id | Tên | Phòng ban | Anomaly chính |
|---|---|---|---|
| `NGF0157` | Alice Carter | Finance | (control) |
| `LRR0148` | Bob Reyes | Engineering | Late-night logon + truy cập `wikileaks.org` / `pastebin.com` / `mega.nz` |
| `MOH0273` | Carol Nguyen | Engineering | USB connect + copy `.exe` ra removable |
| `LAP0338` | David Park | Operations | Gửi email 8–25MB ra `gmail.com` / `protonmail.com` với nhiều attachment |
| `BTR0002` | Eva Thompson | HR | (control) |
| `ACM0001` | Frank Mendez | Sales | After-hours logon nhiều |
| `CNL0003` | Grace Liu | Legal | (control) |
| `ADM0099` | Henry Adams | Operations | (control) |

## Files

```
data/mock/
├── logon.csv          # logon + logoff events
├── device.csv         # USB connect/disconnect
├── file.csv           # file access (normal + .exe trên removable)
├── http.csv           # web browsing (normal + blocked URLs)
├── email.csv          # email send (normal + large external)
├── psychometric.csv   # Big-Five scores cho ML enrichment
└── LDAP/
    └── 2010-01.csv    # HR / org chart
```

Tất cả format giống CERT r4.2 (MM/DD/YYYY HH:MM:SS, brace-id `{...}`).

## Cách dùng nhanh

### Bước 1 — Đảm bảo backend đang chạy

```bash
docker compose up -d            # nếu chưa chạy
docker compose ps             # kiểm tra container "app" đang healthy
curl http://localhost:5173/health    # trả về {"status":"ok"}
```

### Bước 2 — Generate mock data (nếu chưa có)

```bash
python scripts/generate_mock_data.py
```

Output vào `data/mock/`. Script này deterministic với `seed=42` nên chạy lại cho ra cùng dataset. Đổi seed để có dataset mới:

```bash
python scripts/generate_mock_data.py --seed 123
```

### Bước 3 — Import vào database

**Cách A — qua HTTP API (khuyến nghị, mô phỏng đường đi của agent thật):**

```bash
python scripts/import_mock_data.py
# hoặc chỉ định server:
python scripts/import_mock_data.py --server-url http://localhost:5173
```

Script sẽ:
1. Login admin (`admin@demo.com` / `admin123`).
2. POST từng user qua `/api/users` (idempotent — skip nếu đã tồn tại).
3. POST từng device qua `/api/devices`.
4. POST từng event qua `/api/logs/ingest` (chậm vì 1-record-per-call; mất ~30s cho 1,130 events).

**Cách B — direct vào DB (nhanh hơn, bỏ qua HTTP):**

```bash
python scripts/import_mock_data.py --direct
```

Dùng `psycopg` insert thẳng. Yêu cầu biến `DATABASE_URL` trỏ tới PostgreSQL (đọc từ `.env` hoặc export).

### Bước 4 — Verify trên dashboard

Mở http://localhost:5173, login bằng admin, vào **Users**:

- Tìm `LRR0148` (Bob) — risk score có thể cao vì nhiều HTTP anomaly.
- Tìm `MOH0273` (Carol) — risk score cao vì file `.exe` + USB.
- Tìm `LAP0338` (David) — risk score cao vì email external lớn.
- Tìm `ACM0001` (Frank) — risk score tăng vì after-hours logon.

Vào **Logs**: filter theo user `LRR0148`, thấy các URL `wikileaks.org`, `pastebin.com`. Filter theo `MOH0273`, thấy các file `.exe` và `.zip`. Filter theo `LAP0338`, thấy email có `size > 5MB` đến gmail/protonmail.

Vào **Agents** (admin): nếu muốn test Phase 2, dùng blocklist (xem bước 5).

### Bước 5 — Test blocklist (tùy chọn, liên quan Phase 2 agent)

Vào admin UI → **Agents** → **Blocklist** → thêm:

```
Pattern:        wikileaks.org
Pattern type:   domain
Category:       exfiltration
Reason:         test from mock data
```

Sau đó login với tài khoản analyst, xem log của `LRR0148`. Khi chạy demo analyze (UI nút "Analyze"), risk score sẽ tăng do bị match blocklist.

## Verify dữ liệu đã import

```bash
# Users
curl -s "http://localhost:5173/api/users?limit=200" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys, json; print(len(json.load(sys.stdin)))"

# Logs của LRR0148
curl -s "http://localhost:5173/api/logs?user_id=LRR0148&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Hoặc kiểm tra trực tiếp:

```bash
docker compose exec -T app python -c "
from src.backend.app.db.session import get_connection
with get_connection() as c:
    rows = c.execute(\"SELECT id, full_name, department FROM users WHERE id IN ('NGF0157','LRR0148','MOH0273','LAP0338','BTR0002','ACM0001','CNL0003','ADM0099') ORDER BY id\").fetchall()
    for r in rows: print(r['id'], r['full_name'], r['department'])
"
```

## Reset / re-import

Cách nhanh nhất để reset về trạng thái ban đầu:

```bash
# Xoá dữ liệu mock cũ
docker compose exec -T app python -c "
from src.backend.app.db.session import get_connection
with get_connection() as c:
    c.execute(\"DELETE FROM event_logs WHERE source_file LIKE 'mock/%\")
    c.execute(\"DELETE FROM users WHERE id IN ('NGF0157','LRR0148','MOH0273','LAP0338','BTR0002','ACM0001','CNL0003','ADM0099')\")
    c.execute(\"DELETE FROM devices WHERE hostname LIKE 'WS-PC-%'\")
print('Mock data cleared')
"

# Re-import
python scripts/import_mock_data.py --direct
```

Hoặc drop toàn bộ volume (mất hết data khác):

```bash
docker compose down -v
docker compose up --build -d
python scripts/import_mock_data.py
```

## Khác với `data/sample/cert-r4.2-small/`

| | `data/mock/` | `data/sample/cert-r4.2-small/` |
|---|---|---|
| Số events | ~1,130 (5 ngày) | ~440 (3 ngày) |
| User IDs | Tên ngắn `NGF0157`, `LRR0148`... | Dài kiểu CERT `AAL0067`... |
| Anomaly | Cố ý 25%, dễ đọc | Có nhưng ít, tên lạ |
| Mục đích | Demo UI, manual test | Smoke test pipeline |

Khi muốn demo cho người mới → dùng `data/mock/`. Khi muốn test full ML pipeline với dataset gần thật → dùng `data/sample/cert-r4.2-small/`.

## Lệnh một dòng (TL;DR)

```bash
# Generate + import + verify
python scripts/generate_mock_data.py && \
python scripts/import_mock_data.py --direct && \
echo "✓ Mock data ready. Mở http://localhost:5173 và tìm user LRR0148"
```
