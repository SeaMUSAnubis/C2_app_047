# Báo Cáo Tiến Độ MVP (Cập nhật)

**Dựa trên:** `docs/PRD.md`, `docs/UEBA_REQUIREMENTS.md`  
**Ngày:** 2026-06-22  
**Phiên bản:** v0.1.0 (Phase 1+2+3+4+5 done)  
**Branch:** refactor/src-only-fe-be-db-keep-ml  

---

## 1. Tổng Quan Tiến Độ

| Phạm vi | Tổng | Hoàn thành | Một phần | Chưa làm |
|---------|------|------------|----------|----------|
| In Scope (P0) | 12 | **12** | 0 | 0 |
| In Scope (P1) | 3 | **3** | 0 | 0 |
| In Scope (P2) | 1 | **1** | 0 | 0 |
| **Tổng** | **16** | **16** | **0** | **0** |

**Tiến độ tổng: 100% MVP hoàn thành.**

---

## 2. Chi Tiết Theo Tính Năng

### 2.1 P0 - Core Features

| # | Tính năng | Trạng thái | Chi tiết |
|---|-----------|------------|----------|
| 1 | Login/logout + JWT | ✅ Hoàn thành | JWT HS256, bcrypt, 4 role |
| 2 | User Management | ✅ Hoàn thành | CRUD + risk score |
| 3 | Device Management | ✅ Hoàn thành | CRUD + status + last_seen |
| 4 | Log ingestion API | ✅ Hoàn thành | `/api/logs/ingest` |
| 5 | Alert API | ✅ Hoàn thành | `/api/alerts` + status PATCH |
| 6 | Dashboard summary | ✅ Hoàn thành | `/api/dashboard/summary` + `/overview` |
| 7 | ML scoring (OCSVM) | ✅ Hoàn thành | OCSVM + LLM explanation |
| 8 | Model management | ✅ Hoàn thành | `/api/models/*` |
| 9 | LLM explanation | ✅ Hoàn thành | Mistral + fallback template |
| 10 | Risk score propagation | ✅ Hoàn thành | Tự động update users.risk_score |
| 11 | UI: Dashboard | ✅ Hoàn thành | React + Vite + TypeScript |
| 12 | UI: Login | ✅ Hoàn thành | + LegalBanner (PDPD/GDPR) |

### 2.2 P1 - Nâng cao

| # | Tính năng | Trạng thái | Chi tiết |
|---|-----------|------------|----------|
| 13 | CSV import (CERT r4.2) | ✅ Hoàn thành | `scripts/import_mock_data.py` |
| 14 | Demo dataset | ✅ Hoàn thành | 8 users, 5 days, có sẵn anomaly |
| 15 | Multi-user analyze | ✅ Hoàn thành | `/api/analysis/analyze-all` |

### 2.3 P2 - Endpoint Agent

| # | Tính năng | Trạng thái | Chi tiết |
|---|-----------|------------|----------|
| 16 | Endpoint agent + 7 collectors | ✅ Hoàn thành | Phase 1+2+4 (logon, http, device, file, email, process, network) |

---

## 3. Phase Summary

| Phase | Status | Lines | Tests | Key deliverables |
|---|---|---|---|---|
| **1 — Server agent infra** | ✅ done | ~1,800 | 14 | 4 bảng DB, 19 endpoint agent, X-API-Key auth, raw-logs ingest |
| **2 — Agent core + 2 collectors** | ✅ done | ~2,400 | 148 | `agent` Python package, SQLite buffer, HTTPS transport, logon + http |
| **3 — Normalizer + ML scoring** | ✅ done | ~1,975 | 38 | Background asyncio loop, 4 admin endpoint, ml_anomaly_scores table |
| **4 — Full collectors + UI** | ✅ done | ~3,560 | 66 | 5 collector mới, 3 UI page, LegalBanner, E2E test |
| **5 — Deployment pipeline** | ✅ done | ~1,800 | 0 | pyproject + 3 OS installer + PyInstaller |
| **5b — Curl install + self-update** | ✅ done | ~1,200 | 15 | `agent update` + curl-pipe installer |
| **Tổng** | **100% MVP** | **~12,700** | **281 test mới, 0 regression** | |

(Backend + agent tests = 308 pass; 4 pre-existing fail trong DB
schema tests, không do thay đổi của từng phase.)

---

## 4. So với PRD (`docs/PRD.md`)

| PRD requirement | Status | Implementation |
|---|---|---|
| Phát hiện insider threat | ✅ | OCSVM (CERT r4.2 pre-trained) |
| Phát hiện account compromise | ✅ | logon collector + OCSVM features |
| Endpoint monitoring | ✅ | 7 collector, 3 OS |
| LLM explanation | ✅ | Mistral (Vietnamese, 3-line) |
| Real-time dashboard | ✅ | React + 10s polling normalizer |
| Web UI | ✅ | React SPA, 11 pages |
| API | ✅ | FastAPI, 25+ endpoints |
| DB | ✅ | PostgreSQL, 13 tables |
| ML pipeline | ✅ | OCSVM training scripts |
| Auth + RBAC | ✅ | JWT + bcrypt + 4 role |
| Audit log | 🟡 partial | (Phase 6 — out of scope MVP) |
| Multi-tenant | ❌ | Single-tenant only (deliberate) |
| SSO (SAML/OIDC) | ❌ | Out of scope MVP |
| Mobile agent | ❌ | Out of scope MVP |

---

## 5. Demo Accounts (seeded)

| Email | Password | Role |
|---|---|---|
| `admin@demo.com` | `admin123` | admin |
| `security@demo.com` | `security123` | security_manager |
| `analyst@demo.com` | `analyst123` | analyst |
| `employee@demo.com` | `employee123` | employee |

---

## 6. Demo Data (seeded by `scripts/generate_mock_data.py`)

- 8 users (from CERT r4.2)
- 5 ngày log
- 3 anomaly được nhúng sẵn:
  - `LRR0148` (Bob) — wikileaks visit
  - `MOH0273` (Carol) — USB + .exe
  - `LAP0338` (David) — email lớn ra gmail

Login as `admin@demo.com` → Dashboard → Alerts để xem.

---

## 7. Điều chưa làm (deferred, không nằm trong MVP scope)

1. **Audit log UI** — DB có thể lưu log, nhưng chưa có page để xem.
2. **MFA cho admin** — chỉ password + JWT.
3. **Mobile agent** — chỉ Linux/macOS/Windows desktop.
4. **Real-time WebSocket** — UI polling 5-10s là đủ cho demo.
5. **Code signing** — agent binary chưa ký (SmartScreen warning trên Windows).
6. **Prometheus metrics** — chưa expose `/metrics`.
7. **Multi-region** — single-region deploy.

Tất cả đều có thể làm tiếp theo mà không phá vỡ kiến trúc hiện tại.

---

## 8. Kết luận

**MVP hoàn thành đầy đủ 16/16 tính năng.** Hệ thống đã sẵn sàng để demo cho
khách hàng, cài lên máy nhân viên thật (qua curl), và vận hành ở quy mô
hundreds-of-agents. Scale lên thousands-of-agents cần một số tinh chỉnh
về DB (partitioning) + backend (nhiều replicas) — đã document trong
`OPERATIONS.md` §7.
