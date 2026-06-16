# Product Requirements Document (PRD)

**Vị trí chuẩn trong repo:** `docs/planning/PRD.md`  
**Sản phẩm:** UEBA Endpoint Monitoring  
**Phiên bản:** 0.1.0 (2-Week MVP)  
**Ngày:** 09/06/2026  
**Stack đề xuất:** FastAPI + React/Next.js + SQLite/PostgreSQL + JWT + Pandas + Scikit-learn; ML training/inference pipeline trên CERT r4.2; LLM analysis qua OpenAI/Claude hoặc rule-based fallback.  
**Tác giả:** G04 - Team 047 
**Trạng thái:** Active

---

## Mục Lục

1. [Tổng Quan Sản Phẩm](#1-tổng-quan-sản-phẩm)
2. [Mục Tiêu & Chỉ Số Thành Công](#2-mục-tiêu--chỉ-số-thành-công)
3. [Người Dùng & User Stories](#3-người-dùng--user-stories)
4. [Phạm Vi MVP](#4-phạm-vi-mvp)
5. [Đặc Tả Tính Năng Chi Tiết](#5-đặc-tả-tính-năng-chi-tiết)
6. [Luồng Người Dùng](#6-luồng-người-dùng)
7. [Yêu Cầu Phi Chức Năng](#7-yêu-cầu-phi-chức-năng)
8. [Phụ Lục](#8-phụ-lục)

---

## 1. Tổng Quan Sản Phẩm

### 1.1 Mô Tả

**UEBA Endpoint Monitoring** là hệ thống giám sát hành vi người dùng và thiết bị dành cho máy tính/laptop do công ty cấp cho nhân viên. MVP sử dụng bộ dữ liệu **CERT Insider Threat r4.2** làm nguồn dữ liệu chính để mô phỏng log endpoint doanh nghiệp, huấn luyện mô hình ML phát hiện bất thường và đánh giá luồng cảnh báo.

Backend import các file log CERT r4.2 như `logon.csv`, `device.csv`, `file.csv`, `http.csv`, `email.csv`, LDAP và psychometric; chuẩn hóa thành endpoint/security events; trích xuất feature theo user/device/time window; huấn luyện mô hình ML để phát hiện anomaly; chấm điểm rủi ro và tạo cảnh báo. Sau khi ML phát hiện bất thường, LLM nhận anomaly context, feature contribution, baseline và timeline để phân tích bằng ngôn ngữ tự nhiên cho admin/analyst.

Sản phẩm không nhằm theo dõi đời tư cá nhân. Phạm vi MVP chỉ áp dụng cho thiết bị công ty cấp và chỉ thu thập log/metadata phục vụ bảo mật.

**Định hướng sản phẩm:** Endpoint Monitoring / Employee Device Control Agent cho bài toán insider threat và account compromise.

**Thành phần chính:**
- CERT r4.2 Dataset Importer
- Data Preprocessing & Feature Engineering Pipeline
- ML Training & Inference Service
- Backend API
- Database lưu user, device, log, alert, risk score
- Anomaly Detection Service dùng ML là lõi chính
- Risk Scoring Service
- LLM Analysis Service hoặc rule-based fallback
- Admin Dashboard
- Authentication và phân quyền cơ bản

### 1.2 Vấn Đề Giải Quyết

Doanh nghiệp khó phát hiện sớm hành vi rủi ro trên máy tính công ty vì tín hiệu nằm rải rác ở nhiều nguồn log:

1. Nhân viên nội gián truy cập dữ liệu ngoài phạm vi công việc.
2. Tài khoản bị chiếm quyền và đăng nhập vào giờ bất thường hoặc IP lạ.
3. Người dùng tải xuống/copy số lượng lớn file nhạy cảm trong thời gian ngắn.
4. Máy tính công ty bị cắm USB lạ hoặc chạy process đáng ngờ.
5. User truy cập folder/tài nguyên không thuộc vai trò/phòng ban.
6. Hành vi sử dụng thiết bị lệch mạnh so với thói quen bình thường.

Các hệ thống log truyền thống thường chỉ lưu sự kiện rời rạc, thiếu risk score theo user/device và thiếu giải thích dễ hiểu cho analyst. UEBA Endpoint Monitoring gom các tín hiệu đó thành một luồng điều tra rõ ràng.

### 1.3 Giải Pháp

Hệ thống cung cấp một app web hoàn chỉnh:

- Import dữ liệu CERT r4.2 làm nguồn log chính, không phụ thuộc mock data.
- Backend chuẩn hóa log, trích xuất feature và huấn luyện mô hình ML phát hiện bất thường.
- Model inference tạo anomaly score theo user/device/time window.
- Risk scoring chuẩn hóa về thang 0-100.
- Alert tự động tạo khi anomaly score/risk score vượt ngưỡng.
- LLM phân tích alert dựa trên output của model, feature bất thường, baseline và timeline.
- Dashboard hiển thị overview, user, device, log, alert, alert detail và timeline.
- Explanation giúp analyst hiểu vì sao model đánh dấu bất thường.
- Luồng demo end-to-end chạy trên CERT r4.2 để trình bày sản phẩm ngay.

---

## 2. Mục Tiêu & Chỉ Số Thành Công

### 2.1 Mục Tiêu Sản Phẩm MVP

**The Loop:** `Import CERT r4.2 → Feature engineering → Train ML model → Inference anomaly score → Tạo alert → LLM phân tích → Analyst xem explanation/timeline → Cập nhật trạng thái alert`

| # | Mục Tiêu | Đo Lường | Ưu Tiên |
|---|----------|----------|---------|
| O1 | Đăng nhập dashboard bằng tài khoản demo | Admin/Analyst login thành công bằng JWT | P0 |
| O2 | Import và chuẩn hóa CERT r4.2 | Đọc được logon/device/file/http/email/LDAP/psychometric vào schema chung | P0 |
| O3 | Train mô hình ML phát hiện bất thường | Pipeline train reproducible, lưu model artifact và model metrics | P0 |
| O4 | Inference anomaly score và risk score | Log/window bất thường có anomaly score, risk score 0-100 và severity | P0 |
| O5 | Alert tự động được tạo khi risk vượt ngưỡng | Alert mới xuất hiện trên dashboard sau inference | P0 |
| O6 | LLM phân tích anomaly | Alert detail có event/window gốc, feature bất thường, timeline và explanation | P0 |
| O7 | Quản lý user/device cơ bản | Xem danh sách, chi tiết, risk score và last seen | P1 |
| O8 | Deploy online có URL demo | Dashboard và API truy cập được qua public URL | P1 |

### 2.2 Chỉ Số Thành Công

| Metric | Baseline | Target MVP | Lý Do |
|--------|----------|------------|-------|
| Data import completion | 0 | 100% file CERT r4.2 cần dùng được import thành công | Dữ liệu là nền tảng của sản phẩm |
| Training reproducibility | N/A | Train lại cho ra cùng config, metrics và artifact version | Đảm bảo demo/đánh giá ổn định |
| Known scenario detection | N/A | Known red-team/insider windows nằm trong nhóm alert ưu tiên cao | Chứng minh model phát hiện được bất thường quan trọng |
| Inference-to-alert latency | N/A | <10 giây P95 cho batch/window inference demo | Alert phải xuất hiện nhanh sau khi chạy analysis |
| Explanation coverage | 0 | 100% ML-generated alert có LLM/rule-based explanation | Analyst cần hiểu lý do model cảnh báo |
| Dashboard load time | N/A | <3 giây với dữ liệu đã aggregate/index | UI đủ mượt để trình bày |
| Auth protection | N/A | 100% API quản trị yêu cầu token | Đáp ứng yêu cầu phân quyền cơ bản |

---

## 3. Người Dùng & User Stories

### 3.1 Persona

#### Persona A — Security Admin

- **Vai trò:** Quản trị bảo mật/IT trong doanh nghiệp.
- **Nỗi đau:** Không có góc nhìn tập trung về user, device, log và cảnh báo.
- **Mục tiêu:** Theo dõi toàn bộ thiết bị công ty cấp, xem risk score, quản lý user/device và điều phối xử lý alert.
- **Quyền:** Toàn quyền xem dashboard, user, device, log, alert và cập nhật trạng thái.

#### Persona B — SOC / Security Analyst

- **Vai trò:** Người phân tích cảnh báo bảo mật.
- **Nỗi đau:** Alert thường thiếu ngữ cảnh, phải tự ghép log thủ công.
- **Mục tiêu:** Xem alert detail, risk factors, timeline và explanation để quyết định điều tra tiếp, resolve hoặc đánh dấu false positive.
- **Quyền:** Xem dashboard/log/alert, cập nhật trạng thái alert.

#### Persona C — IT Endpoint Engineer

- **Vai trò:** Người triển khai agent trên máy công ty.
- **Nỗi đau:** Cần một schema endpoint rõ ràng để sau MVP có thể triển khai agent thật mà không phá vỡ pipeline dữ liệu.
- **Mục tiêu:** Hiểu cách dữ liệu CERT r4.2 được ánh xạ sang endpoint events và chuẩn bị cho phase triển khai agent thật.
- **Quyền:** Không nhất thiết dùng dashboard trong MVP, nhưng cần tài liệu schema endpoint rõ ràng.

#### Persona D — Data/ML Engineer

- **Vai trò:** Người xử lý dữ liệu và huấn luyện mô hình anomaly detection.
- **Nỗi đau:** CERT r4.2 nhiều nguồn log lớn, cần pipeline nhất quán để join, aggregate, train và đánh giá.
- **Mục tiêu:** Import dataset, xây feature theo user/device/window, train model, lưu artifact và cung cấp anomaly score cho backend.
- **Quyền:** Chạy data pipeline, xem model metrics và trigger analysis.

### 3.2 User Stories

#### Epic 1: Authentication & Role Management

```
US-01  Là Admin/Analyst, tôi muốn đăng nhập bằng email và mật khẩu,
       để dashboard chỉ cho người có quyền truy cập.

       Acceptance Criteria:
       - Có trang login với email/password.
       - Sai thông tin đăng nhập hiển thị lỗi rõ ràng.
       - Đăng nhập thành công trả JWT token.
       - Token được dùng để gọi API quản trị.
       - Có tài khoản demo:
         admin@demo.com / admin123
         analyst@demo.com / analyst123

US-02  Là Admin, tôi muốn phân biệt role admin và analyst,
       để giới hạn các thao tác quản trị nhạy cảm.

       Acceptance Criteria:
       - Admin xem và quản lý user/device.
       - Analyst xem dashboard, alert, log và cập nhật trạng thái alert.
       - API kiểm tra role với các endpoint cần quyền admin.
```

#### Epic 2: User Management

```
US-03  Là Admin, tôi muốn xem danh sách nhân viên,
       để theo dõi risk score theo từng user.

       Acceptance Criteria:
       - Bảng users hiển thị username, full name, email, department, job role, status, risk score.
       - Search/filter theo department, role, status.
       - Click user để xem chi tiết, log, alert và timeline.

US-04  Là Admin, tôi muốn thêm/sửa/khóa user demo,
       để mô phỏng dữ liệu nhân sự và role truy cập.

       Acceptance Criteria:
       - User có các trường: id, username, full_name, email, department, job_role, status, created_at.
       - Có thể cập nhật department/job_role/status.
       - User bị khóa không được gán làm active owner cho device mới.
```

#### Epic 3: Device Management

```
US-05  Là Admin, tôi muốn xem danh sách thiết bị công ty cấp,
       để biết máy nào online/offline và đang gán cho ai.

       Acceptance Criteria:
       - Bảng devices hiển thị device_id, hostname, OS, IP, assigned user, status, last_seen, risk score.
       - Filter theo status, OS, assigned user.
       - Click device để xem log, alert và timeline.

US-06  Là Admin, tôi muốn gán device cho user,
       để hệ thống phân tích hành vi theo đúng người sở hữu thiết bị.

       Acceptance Criteria:
       - Device có assigned_user_id.
       - Một device thuộc tối đa một user tại một thời điểm.
       - Khi import log CERT hoặc phase sau agent gửi log, `last_seen` và trạng thái device được cập nhật.
```

#### Epic 4: CERT r4.2 Data Import & Normalization

```
US-07  Là Data/ML Engineer, tôi muốn import bộ CERT r4.2,
       để hệ thống có dữ liệu endpoint thực tế cho training và demo.

       Acceptance Criteria:
       - Import được các file: logon.csv, device.csv, file.csv, http.csv, email.csv,
         LDAP/*.csv và psychometric.csv nếu có.
       - Không dùng mock data làm nguồn demo/training chính.
       - Có trạng thái import: pending, running, completed, failed.
       - Có summary sau import: số dòng, số user, số PC/device, khoảng thời gian,
         số event theo loại.

US-08  Là Data/ML Engineer, tôi muốn chuẩn hóa CERT r4.2 thành schema endpoint events,
       để dashboard và model dùng cùng một dạng dữ liệu.

       Acceptance Criteria:
       - logon.csv map thành login/logout events.
       - device.csv map thành removable device connect/disconnect events.
       - file.csv map thành removable-media file copy events.
       - http.csv map thành web access events.
       - email.csv map thành email activity events.
       - LDAP map thành user/department/role/supervisor/device context.
       - psychometric.csv được lưu như optional enrichment feature, không hiển thị thô nếu không cần.
```

#### Epic 5: Log Ingestion & Timeline

```
US-09  Là hệ thống, tôi muốn lưu normalized endpoint events từ CERT r4.2,
       để phục vụ phân tích hành vi user/device.

       Acceptance Criteria:
       - Log lưu đủ source_file, source_id, user_id, device_id/pc, timestamp, event_type,
         action, resource, content/topic metadata, bytes/size, recipient/domain nếu có, raw_json.
       - Có thể truy vết từ normalized event về dòng CSV gốc.
       - Không duplicate khi import lại cùng dataset.
       - API `POST /api/logs/ingest` vẫn tồn tại cho phase agent thật, nhưng không phải nguồn dữ liệu MVP chính.

US-10  Là Analyst, tôi muốn xem timeline hành vi quanh một alert,
       để hiểu chuỗi sự kiện trước/sau anomaly.

       Acceptance Criteria:
       - Timeline hiển thị các event theo thời gian.
       - Có filter theo user/device.
       - Alert detail hiển thị timeline gần thời điểm alert.
```

#### Epic 6: ML Anomaly Detection & Risk Scoring

```
US-11  Là Data/ML Engineer, tôi muốn train mô hình ML trên CERT r4.2,
       để phát hiện hành vi bất thường dựa trên baseline user/device.

       Acceptance Criteria:
       - Có pipeline tạo feature theo user/device/time window.
       - Model MVP hỗ trợ ít nhất một thuật toán anomaly detection, ví dụ:
         Isolation Forest, Local Outlier Factor, One-Class SVM hoặc Autoencoder.
       - Có baseline theo user và/hoặc peer group/department.
       - Có model artifact version, training config và metrics.
       - Có thể chạy batch inference trên một khoảng thời gian của CERT r4.2.
       - Rule-based detection chỉ dùng làm baseline so sánh, guardrail hoặc feature bổ trợ.

US-12  Là Analyst, tôi muốn risk score chuẩn hóa 0-100,
       để ưu tiên xử lý cảnh báo.

       Acceptance Criteria:
       - Risk score nằm trong 0-100.
       - Mức độ:
         0-30 Low
         31-60 Medium
         61-80 High
         81-100 Critical
       - Risk score được tính từ anomaly score của model, feature severity và optional rule adjustment.
       - User/device risk score cập nhật theo alert/window mới.
       - Alert lưu model_version và top anomalous features nếu model/pipeline cung cấp được.
```

#### Epic 7: Alert Management & Explanation

```
US-13  Là Analyst, tôi muốn hệ thống tự tạo alert khi risk cao,
       để không phải tự đọc từng dòng log.

       Acceptance Criteria:
       - Alert tạo khi risk_score >= 60.
       - Alert có user_id, device_id, log_id, risk_score, severity, alert_type, title, description, explanation, status.
       - Status gồm: new, investigating, resolved, false_positive.
       - Có API PATCH /api/alerts/{id}/status.

US-14  Là Analyst, tôi muốn đọc explanation bằng ngôn ngữ tự nhiên,
       để hiểu nhanh vì sao mô hình ML đánh dấu bất thường.

       Acceptance Criteria:
       - Mỗi alert có explanation.
       - Nếu có LLM API key, explanation được sinh từ anomaly score, top anomalous features,
         baseline user/device, peer baseline, event timeline và log gốc.
       - Nếu không có API key, hệ thống dùng rule-based fallback.
       - Explanation nêu rõ hành vi bất thường, user/device liên quan, feature lệch chuẩn,
         mức độ tin cậy và đề xuất hướng điều tra.
```

#### Epic 8: Admin Dashboard

```
US-15  Là Admin, tôi muốn xem overview dashboard,
       để nắm nhanh tình trạng bảo mật endpoint.

       Acceptance Criteria:
       - Có cards: tổng user, tổng device, device online, log hôm nay, tổng alert, high/critical alert, top user risk.
       - Có chart alert theo thời gian.
       - Có chart phân bố severity.
       - Có top event type và top user/device nhiều cảnh báo.

US-16  Là Analyst, tôi muốn xem danh sách alert có filter,
       để ưu tiên xử lý theo severity/status/user/device.

       Acceptance Criteria:
       - Bảng alerts có màu severity trực quan.
       - Filter theo severity, status, user, device.
       - Click alert mở trang detail.
       - Có thao tác cập nhật status.
```

---

## 4. Phạm Vi MVP

### 4.1 In Scope

| # | Tính Năng | Ưu Tiên | Ghi Chú |
|---|-----------|---------|---------|
| 1 | Login/logout + JWT | P0 | Tài khoản demo admin/analyst |
| 2 | User Management | P0 | Danh sách, chi tiết, role công việc, risk score |
| 3 | Device Management | P0 | Device assignment, online/offline, last seen |
| 4 | CERT r4.2 Import Pipeline | P0 | Import logon/device/file/http/email/LDAP/psychometric |
| 5 | Data Normalization | P0 | Chuẩn hóa CSV thành endpoint/security events |
| 6 | Feature Engineering Pipeline | P0 | Feature theo user/device/time window |
| 7 | ML Anomaly Detection | P0 | Train model và batch inference |
| 8 | Risk Scoring 0-100 | P0 | Từ anomaly score + feature severity |
| 9 | Alert Management | P0 | Tạo alert, filter, đổi status |
| 10 | LLM Anomaly Analysis | P0 | Phân tích alert từ output model và timeline |
| 11 | Alert Detail | P0 | Event/window gốc, model score, top features, explanation, timeline |
| 12 | Overview Dashboard | P0 | Cards và charts chính |
| 13 | Live Agent API | P1 | `POST /api/logs/ingest` cho phase endpoint agent thật |
| 14 | Deploy online | P1 | Public dashboard/API URL |
| 15 | Rule-based Baseline/Guardrail | P2 | So sánh với ML, hỗ trợ fallback |

### 4.2 Out of Scope

| Tính Năng | Lý Do |
|-----------|------|
| Giám sát thiết bị cá nhân BYOD | MVP chỉ áp dụng máy công ty cấp |
| Keylogger, screen recording, đọc nội dung file cá nhân | Không phù hợp phạm vi privacy/compliance |
| DLP enterprise đầy đủ | UEBA MVP chỉ phát hiện anomaly và cảnh báo |
| EDR response tự động như kill process/quarantine | Rủi ro cao, để phase sau |
| Multi-tenant/workspace | MVP dùng một tổ chức demo |
| SIEM/SOAR integration | Phase sau |
| Mobile agent | MVP tập trung laptop/desktop |
| Production-grade RBAC phức tạp | MVP chỉ cần admin/analyst |
| Mock data làm nguồn demo/training chính | Nhóm dùng CERT r4.2 làm dataset chính |

---

## 5. Đặc Tả Tính Năng Chi Tiết

### 5.1 Kiến Trúc Hệ Thống

```text
CERT r4.2 CSV Dataset
        |
        | Import + Normalize + Feature Engineering
        v
Backend API
        |
        |-- Auth & Role Management
        |-- User Management
        |-- Device Management
        |-- CERT Dataset Import API
        |-- Normalized Event Store
        |-- Feature Extraction Service
        |-- ML Training Service
        |-- ML Inference / Anomaly Detection Service
        |-- Risk Scoring Service
        |-- LLM Analysis Service
        |-- Alert Management Service
        |
        v
Database
        |
        v
Frontend Admin Dashboard
```

`POST /api/logs/ingest` được giữ cho phase tích hợp Endpoint Agent thật, nhưng MVP ưu tiên batch pipeline từ CERT r4.2.

### 5.2 Data Model

#### App Account

```text
id
email
password_hash
full_name
role: admin | analyst
created_at
```

#### User

```text
id
username
full_name
email
department
job_role
status
risk_score
created_at
```

#### Device

```text
id
device_id
hostname
os
ip_address
assigned_user_id
status: online | offline
last_seen
risk_score
created_at
```

#### Event Log

```text
id
source_file
source_id
user_id
device_id
timestamp
event_type
action
resource
resource_sensitivity
ip_address
process_name
usb_device
bytes_transferred
content_topics
email_recipients
url_domain
status
risk_score
risk_level
risk_factors
raw_json
created_at
```

#### Feature Window

```text
id
user_id
device_id
window_start
window_end
feature_vector
feature_summary
baseline_context
created_at
```

#### ML Model Artifact

```text
id
model_name
model_version
algorithm
training_dataset_version
training_config
metrics_json
artifact_path
status
created_at
```

#### Alert

```text
id
user_id
device_id
log_id
risk_score
severity
alert_type
title
description
explanation
risk_factors
model_version
anomaly_score
top_anomalous_features
status: new | investigating | resolved | false_positive
created_at
updated_at
```

### 5.3 Event Types

```text
login
logout
file_access
file_download
file_copy
usb_insert
process_start
network_access
permission_change
failed_login
email_send
http_access
ldap_profile
psychometric
```

### 5.4 CERT r4.2 Source Mapping

| File | Fields Chính | Mapping Sản Phẩm |
|------|--------------|------------------|
| `logon.csv` | id, date, user, pc, activity | login/logout event, off-hour behavior, shared/dedicated PC access |
| `device.csv` | id, date, user, pc, activity | removable device connect/disconnect, device usage deviation |
| `file.csv` | id, date, user, pc, filename, content | file copy to removable media, file topic/content feature |
| `http.csv` | id, date, user, pc, url, content | web access, domain/topic behavior, browsing drift |
| `email.csv` | id, date, user, pc, to, cc, bcc, from, size, attachment_count, content | email volume, recipients, external email, topic/social graph shift |
| `LDAP/*.csv` | user/org/role/device attributes | department, role, manager, assigned PC, employment status |
| `psychometric.csv` | user_id, O, C, E, A, N | optional enrichment feature, không hiển thị thô nếu không cần |

### 5.5 Feature Extraction

Từ log thô, hệ thống tạo các feature:

```text
login_hour
is_off_hour
failed_login_count
download_volume
file_access_count
sensitive_access_count
usb_insert_count
unknown_usb_flag
suspicious_process_flag
unique_ip_count
role_mismatch_flag
access_frequency
bytes_transferred
email_count
email_external_ratio
email_attachment_count
http_domain_entropy
http_topic_drift
file_copy_count
device_connect_count
unique_pc_count
dedicated_pc_mismatch_flag
peer_group_deviation
days_to_or_from_termination
```

### 5.6 ML Training & Inference

Pipeline ML dùng CERT r4.2 theo các bước:

```text
Raw CERT CSV
    -> Normalize events
    -> Join LDAP/psychometric context
    -> Aggregate by user/device/time window
    -> Build feature vectors
    -> Train anomaly model
    -> Batch inference
    -> Convert anomaly score to risk score
    -> Create alerts
    -> Send context to LLM analysis
```

Thuật toán ứng viên:

| Algorithm | Vai Trò |
|-----------|---------|
| Isolation Forest | Baseline ML chính cho anomaly detection tabular |
| Local Outlier Factor | So sánh local density theo peer group/user behavior |
| One-Class SVM | Thử nghiệm với feature scale tốt và tập nhỏ hơn |
| Autoencoder | Phase nâng cao nếu cần học pattern phi tuyến |

Rule-based checks vẫn có thể dùng làm:

- Feature đầu vào cho model.
- Guardrail để không bỏ qua tín hiệu bảo mật rõ ràng.
- Baseline so sánh với ML trong báo cáo.
- Fallback explanation khi LLM không khả dụng.

### 5.7 Risk Scoring

```text
risk_score = normalize(anomaly_score, model_thresholds) + feature_severity_adjustment
risk_score = min(max(risk_score, 0), 100)
```

Severity:

```text
0-30: Low
31-60: Medium
61-80: High
81-100: Critical
```

Alert threshold:

```text
risk_score >= 60
```

Mỗi alert phải lưu:

- `model_version`
- `anomaly_score`
- `risk_score`
- `top_anomalous_features`
- `baseline_context`
- `timeline_context`

### 5.8 API Endpoints

#### Auth

```text
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/logout
```

#### Users

```text
GET    /api/users
POST   /api/users
GET    /api/users/{id}
PUT    /api/users/{id}
DELETE /api/users/{id}
GET    /api/users/{id}/logs
GET    /api/users/{id}/alerts
```

#### Devices

```text
GET    /api/devices
POST   /api/devices
GET    /api/devices/{id}
PUT    /api/devices/{id}
DELETE /api/devices/{id}
GET    /api/devices/{id}/logs
GET    /api/devices/{id}/alerts
```

#### Logs

```text
POST /api/logs/ingest
GET  /api/logs
GET  /api/logs/{id}
```

#### Dataset & ML

```text
POST /api/datasets/cert-r42/import
GET  /api/datasets/cert-r42/status
GET  /api/datasets/cert-r42/summary
POST /api/features/build
POST /api/models/train
GET  /api/models
GET  /api/models/{model_version}
POST /api/models/{model_version}/infer
GET  /api/models/{model_version}/metrics
```

#### Alerts

```text
GET   /api/alerts
GET   /api/alerts/{id}
PATCH /api/alerts/{id}/status
```

#### Dashboard

```text
GET /api/dashboard/summary
GET /api/dashboard/alerts-over-time
GET /api/dashboard/severity-distribution
GET /api/dashboard/top-risk-users
GET /api/dashboard/top-risk-devices
GET /api/dashboard/top-event-types
```

#### Analysis

```text
POST /api/analyze/run
POST /api/analyze/log/{log_id}
POST /api/analyze/window/{window_id}
GET  /api/analyze/baseline/{user_id}
```

### 5.9 Dashboard Pages

| Trang | Nội Dung |
|-------|----------|
| Login | Form đăng nhập, lỗi sai credentials, redirect sau login |
| Overview | Cards tổng quan, charts alert/time, severity, top risk users/devices |
| Users | Bảng users, filter, risk score, user detail |
| Devices | Bảng devices, online/offline, assigned user, last seen, risk score |
| Logs | Bảng event logs, filter theo user/device/event/time/severity, log detail |
| Dataset | Import/status/summary CERT r4.2, số dòng theo source file, lỗi import |
| Models | Danh sách model version, thuật toán, training config, metrics, nút chạy inference |
| Alerts | Bảng alerts, filter severity/status/user/device, đổi status |
| Alert Detail | User, device, event/window gốc, anomaly score, top features, explanation, timeline |
| Timeline | Timeline theo user/device |

### 5.10 Privacy & Compliance Note

UI và README cần nêu rõ:

- Chỉ áp dụng trên thiết bị do công ty cấp.
- Chỉ thu thập metadata/log phục vụ bảo mật.
- Không thu thập mật khẩu.
- Không đọc nội dung tin nhắn cá nhân.
- Không ghi lại nội dung file cá nhân.
- Có thông báo minh bạch cho nhân viên.
- Chỉ admin/analyst có quyền xem cảnh báo.
- Log nhạy cảm cần được giới hạn quyền truy cập.

---

## 6. Luồng Người Dùng

### 6.1 Demo Flow Bắt Buộc

```text
[Admin mở dashboard]
       ↓
[Đăng nhập bằng admin@demo.com / admin123]
       ↓
[Dataset page hiển thị trạng thái import CERT r4.2]
       ↓
[Chạy import CERT r4.2 hoặc xác nhận dataset đã import]
       ↓
[Build feature windows theo user/device/time]
       ↓
[Train ML anomaly detection model]
       ↓
[Xem model metrics và model version]
       ↓
[Chạy batch inference trên khoảng thời gian demo]
       ↓
[Backend tạo alert từ anomaly score/risk score]
       ↓
[Admin/Analyst mở alert detail]
       ↓
[Xem event/window gốc, anomaly score, top features, LLM explanation và timeline]
       ↓
[Cập nhật trạng thái alert: investigating hoặc resolved]
```

### 6.2 Daily Analyst Flow

```text
[Analyst đăng nhập đầu ngày]
       ↓
[Overview: xem high/critical alerts]
       ↓
[Alerts: filter status = new, severity = high/critical]
       ↓
[Mở alert detail]
       ↓
[Đọc LLM analysis + kiểm tra anomaly score/top features/timeline]
       ↓
[Chuyển status sang investigating]
       ↓
[Sau khi xác minh, chọn resolved hoặc false_positive]
```

### 6.3 Data/ML Engineer Flow

```text
[Chuẩn bị đường dẫn dataset CERT r4.2]
       ↓
[Import logon/device/file/http/email/LDAP/psychometric]
       ↓
[Kiểm tra data quality và summary]
       ↓
[Build feature windows]
       ↓
[Train model và lưu artifact]
       ↓
[Chạy inference và kiểm tra alert/LLM analysis]
```

---

## 7. Yêu Cầu Phi Chức Năng

### 7.1 Performance

| Yêu Cầu | Target | Đo Lường |
|---------|--------|----------|
| CERT import job | Hoàn thành được trên file r4.2 đã chọn cho demo | Job status và import summary |
| Feature build job | Hoàn thành reproducible theo cùng config | Feature window count và checksum/config |
| Batch inference latency | <10 giây P95 cho tập demo đã chọn | Inference start đến alert creation |
| Dashboard load time | <3 giây | First meaningful render với dữ liệu đã aggregate/index |
| Alert detail load time | <2 giây | Click alert đến khi detail hiển thị |
| Dataset scale | Hỗ trợ CERT r4.2 nhiều GB bằng batch/chunk processing | Không cần load toàn bộ dataset vào memory |

### 7.2 Reliability

- Backend không crash khi gặp dòng CSV lỗi; ghi lỗi import theo source file/source_id.
- Nếu LLM provider lỗi hoặc không có API key, explanation fallback vẫn hoạt động.
- Restart app không làm mất database, feature windows, model artifact metadata nếu dùng volume/persistent disk.
- Training/inference job có status rõ ràng: queued, running, completed, failed.
- Health check `GET /health` trả trạng thái API/database.

### 7.3 Security

| Yêu Cầu | Cách Implement |
|---------|----------------|
| Dashboard auth | JWT, token expiry |
| Password storage | Hash password, không lưu plaintext |
| Role check | Admin/Analyst middleware |
| Agent/API authentication | API key hoặc token riêng cho ingest endpoint ở phase live agent |
| CORS | Config theo deploy environment |
| Input validation | Pydantic/schema validation |
| SQL injection | ORM hoặc parameterized query |
| Dataset access | Không commit dataset lớn/nhạy cảm vào repo nếu license không cho phép; cấu hình bằng local path hoặc object storage |
| Sensitive logs | Giới hạn quyền xem, không log password/content cá nhân |

### 7.4 Installability & Deploy

- Chạy local được bằng README rõ ràng.
- Có `.env.example` cho backend URL, JWT secret, database URL, CERT dataset path, model artifact path, optional LLM API key.
- Có Docker/Docker Compose nếu thời gian cho phép.
- Deploy online:
  - Backend: Render/Railway/Fly.io.
  - Frontend: Vercel/Netlify nếu tách frontend.
  - Database: SQLite persistent disk cho demo hoặc PostgreSQL.
  - Dataset/model artifacts: persistent disk hoặc object storage; không bắt buộc upload toàn bộ 16GB dataset lên deploy demo.

### 7.5 Observability

- Backend log có timestamp, level, endpoint, status code.
- Log lỗi validation, import, training và inference có message dễ debug.
- Dashboard hiển thị last_seen của device.
- Dashboard hiển thị import status, model version, training metrics và inference run status.
- Có health endpoint cho demo/deploy.

---

## 8. Phụ Lục

### 8.1 Glossary

| Thuật Ngữ | Định Nghĩa |
|-----------|------------|
| UEBA | User and Entity Behavior Analytics, phân tích hành vi người dùng/thực thể để phát hiện bất thường |
| Endpoint Agent | Chương trình chạy trên máy công ty để thu thập và gửi metadata bảo mật |
| CERT r4.2 | Bộ dữ liệu CERT Insider Threat Release 4.2 dùng làm nguồn log chính cho MVP |
| Event Log | Một sự kiện hành vi như login, file access, USB insert, process start |
| Baseline | Mẫu hành vi bình thường của user/device |
| Anomaly | Hành vi lệch khỏi baseline hoặc vi phạm rule bảo mật |
| Anomaly Score | Điểm bất thường do model ML sinh ra trước khi quy đổi sang risk score |
| Model Artifact | File/model version được sinh sau training, dùng cho inference |
| Risk Score | Điểm rủi ro chuẩn hóa 0-100 |
| Alert | Cảnh báo được tạo khi risk score vượt ngưỡng |
| Risk Factor | Lý do cụ thể làm tăng risk score |
| Explanation | Diễn giải bằng ngôn ngữ tự nhiên cho alert |
| Insider Threat | Rủi ro từ người trong tổ chức hoặc tài khoản nội bộ bị lạm dụng |

### 8.2 Assumptions

1. MVP dùng bộ dữ liệu CERT r4.2 làm nguồn dữ liệu chính, không dùng mock data để train/demo chính.
2. Thiết bị được giám sát là tài sản công ty cấp cho nhân viên.
3. Công ty có chính sách thông báo minh bạch cho nhân viên về việc thu thập metadata bảo mật.
4. ML anomaly detection là lõi phát hiện bất thường của MVP; rule-based chỉ là baseline/guardrail/fallback.
5. LLM phân tích sau khi model ML phát hiện anomaly; explanation phải luôn có fallback, không phụ thuộc bắt buộc vào LLM API key.
6. Endpoint Agent thật là phase sau; MVP vẫn giữ schema/API để định hướng sản phẩm endpoint monitoring.
7. MVP phục vụ một tổ chức demo, chưa cần multi-tenant.

### 8.3 Dependencies & Risks

| Dependency | Risk | Mitigation |
|------------|------|------------|
| CERT r4.2 Dataset | Dataset rất lớn, đặc biệt `http.csv`, khó import/deploy toàn bộ | Batch/chunk processing, cho phép chọn subset thời gian cho demo, không commit dataset vào repo |
| Data Quality | CERT có dirty/missing events theo mô tả dataset | Pipeline validation, import error report, xử lý missing data rõ ràng |
| ML Model | Model có thể false positive/false negative | Theo dõi metrics, threshold tuning, hiển thị top features và cho phép false_positive status |
| LLM API | Không có key, rate limit hoặc outage | Rule-based/template explanation fallback từ anomaly score và top features |
| Ground Truth | Red-team labels/scenarios có thể không đầy đủ trong repo | Nếu có labels thì dùng để đánh giá; nếu không thì dùng known scenario windows và analyst-reviewed test set |
| Privacy Concern | Người dùng hiểu nhầm là theo dõi cá nhân | Privacy note rõ trong UI/README, chỉ metadata trên máy công ty |
| Deploy SQLite | Persistence hạn chế trên một số platform | Dùng persistent disk hoặc PostgreSQL nếu deploy production-like |

### 8.4 Quyết Định Sản Phẩm Đã Chốt

| # | Câu Hỏi | Quyết Định | Lý Do |
|---|---------|------------|-------|
| Q1 | Hướng sản phẩm là gì? | Endpoint Monitoring cho máy công ty cấp | Bám đúng yêu cầu đề tài và demo rõ insider threat |
| Q2 | MVP có phải web/app không? | Có, bắt buộc dashboard + backend + data/ML pipeline | Không chấp nhận notebook/script-only |
| Q3 | Dataset chính? | CERT Insider Threat r4.2 | Phù hợp UEBA/insider threat và có log endpoint đa nguồn |
| Q4 | Detection nền tảng? | ML anomaly detection là lõi chính | Nhóm dự định train model để phát hiện bất thường |
| Q5 | Rule-based dùng để làm gì? | Baseline/guardrail/fallback, không phải hướng chính | Vẫn hữu ích để so sánh và giải thích khi LLM/model thiếu dữ liệu |
| Q6 | Explanation thế nào? | LLM phân tích output ML; fallback rule-based/template | Analyst cần hiểu anomaly do model phát hiện |
| Q7 | Alert threshold? | `risk_score >= 60` | Theo yêu cầu, tương ứng Medium/High boundary |
| Q8 | Scope privacy? | Chỉ metadata bảo mật trên thiết bị công ty | Tránh theo dõi đời tư cá nhân |
| Q9 | Live agent trong MVP? | Giữ API/schema, chưa là nguồn dữ liệu chính | MVP tập trung CERT r4.2 và ML trước |

### 8.5 Tiêu Chí Hoàn Thành

- Chạy được backend.
- Chạy được frontend/dashboard.
- Đăng nhập được bằng tài khoản demo.
- Dashboard hiển thị dữ liệu user/device/log/alert.
- Quản lý được user và device.
- Import được CERT r4.2 vào database hoặc data store.
- Chuẩn hóa log CERT thành endpoint/security events.
- Build được feature windows theo user/device/time.
- Train được mô hình ML anomaly detection và lưu model artifact.
- Chạy inference sinh anomaly score/risk score.
- Backend tạo alert từ kết quả model.
- Risk score hoạt động theo thang 0-100.
- Alert detail có LLM analysis/fallback explanation, top anomalous features và model version.
- Có timeline hành vi user/device.
- Có README hướng dẫn chuẩn bị CERT r4.2, import dataset, train model, chạy inference và deploy.
