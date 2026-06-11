# Yêu cầu triển khai dự án UEBA Endpoint Monitoring

## 1. Thông tin đề tài

- **Mã đề:** AI20K-C2-SEC-07
- **Tên đề tài:** AI Phát Hiện Bất Thường Hành Vi Người Dùng & Tài Khoản (UEBA)
- **Lĩnh vực:** Security — Insider Threat
- **Kỹ thuật định hướng:** Anomaly Detection + LLM Explanation
- **Định hướng sản phẩm:** App giám sát thiết bị công ty cấp cho nhân viên bằng Endpoint Agent + Backend + Admin Dashboard

## 2. Bối cảnh bài toán

Trong doanh nghiệp, máy tính/laptop được công ty cấp cho từng nhân viên có thể bị lạm dụng hoặc bị chiếm quyền. Một số tình huống rủi ro:

- Nhân viên nội gián truy cập dữ liệu ngoài phạm vi công việc.
- Tài khoản bị chiếm quyền và đăng nhập vào giờ bất thường.
- Người dùng tải xuống/copy số lượng lớn file nhạy cảm.
- Máy tính công ty bị cắm USB lạ hoặc chạy process đáng ngờ.
- User truy cập folder/tài nguyên không thuộc vai trò của mình.
- Hành vi sử dụng thiết bị lệch mạnh so với thói quen bình thường.

Vì các tín hiệu này nằm rải rác trong log thiết bị, log file, log đăng nhập và log truy cập tài nguyên, hệ thống cần có khả năng thu thập, phân tích, phát hiện anomaly, chấm điểm rủi ro và giải thích cảnh báo bằng ngôn ngữ dễ hiểu cho admin/analyst.

## 3. Định hướng sản phẩm của nhóm

Nhóm triển khai hệ thống UEBA theo hướng **Endpoint Monitoring / Employee Device Control Agent**.

Bối cảnh sử dụng:

> Công ty cấp máy tính/laptop cho nhân viên. Trên mỗi máy sẽ cài một agent chạy nền để thu thập log hành vi sử dụng thiết bị. Agent gửi log về backend. Backend phân tích baseline hành vi bình thường của từng user/device, phát hiện hành vi lệch chuẩn và hiển thị cảnh báo trên dashboard cho quản trị viên.

Hệ thống không nhằm theo dõi đời tư cá nhân. Phạm vi demo chỉ tập trung vào thiết bị do công ty cấp và các log phục vụ mục đích bảo mật.

## 4. Mục tiêu sản phẩm

Xây dựng một web/app hoàn chỉnh gồm:

1. Endpoint Agent giả lập hoặc agent đơn giản chạy trên máy người dùng.
2. Backend API nhận log từ agent.
3. Database lưu user, device, event log, alert, risk score.
4. Anomaly Detection Service phát hiện hành vi bất thường.
5. Risk Scoring Service chấm điểm rủi ro.
6. LLM Explanation Service giải thích lý do cảnh báo.
7. Admin Dashboard để xem thiết bị, user, log, alert và biểu đồ.
8. Authentication và phân quyền cơ bản.
9. Deploy online có URL truy cập.

## 5. Yêu cầu sản phẩm bắt buộc

Sản phẩm cuối cùng **bắt buộc** phải là web/app hoàn chỉnh, không chỉ là notebook hoặc script.

### Bắt buộc có

- Giao diện UI/UX hoàn chỉnh.
- Backend API rõ ràng.
- Đăng nhập và phân quyền cơ bản.
- Dashboard theo dõi user/device/log/alert.
- Quản lý user và device.
- Có Endpoint Agent giả lập để gửi log.
- Có dữ liệu log để demo.
- Có anomaly detection bằng rule-based và/hoặc machine learning.
- Có risk score.
- Có trang chi tiết cảnh báo.
- Có timeline hành vi user/device.
- Có giải thích anomaly bằng LLM hoặc rule-based fallback.
- Có deploy online và URL truy cập.

### Không được chấp nhận

- Chỉ có notebook.
- Chỉ có script CLI.
- Chỉ chạy localhost mà không deploy.
- Không có giao diện.
- Không có đăng nhập/phân quyền.
- Không có dashboard.
- Không có luồng agent gửi log về backend.

## 6. Kiến trúc hệ thống đề xuất

```text
Endpoint Agent / Mock Agent
        |
        | gửi event log qua REST API
        v
Backend API FastAPI
        |
        |-- Auth & Role Management
        |-- User Management
        |-- Device Management
        |-- Log Ingestion API
        |-- Feature Extraction Service
        |-- Anomaly Detection Service
        |-- Risk Scoring Service
        |-- LLM Explanation Service
        |-- Alert Management Service
        |
        v
Database
        |
        v
Frontend Admin Dashboard
```

## 7. Tech stack đề xuất

### Backend

- Python
- FastAPI
- Uvicorn
- SQLAlchemy hoặc SQLModel
- Pydantic
- JWT Authentication
- SQLite cho demo nhanh hoặc PostgreSQL nếu muốn production-like
- Scikit-learn cho anomaly detection

### Frontend

- React hoặc Next.js
- TailwindCSS hoặc Bootstrap
- Chart.js / Recharts / ECharts để vẽ biểu đồ
- Axios để gọi API

### Endpoint Agent

- Python script chạy nền hoặc chạy theo interval.
- Có thể đặt trong thư mục `agent/`.
- Gửi log về backend qua REST API.
- Có chế độ sinh log bình thường và log bất thường.

Ví dụ chạy agent:

```bash
python agent/main.py --mode normal
python agent/main.py --mode anomaly
python agent/main.py --user employee_01 --device laptop_01 --interval 5
```

### AI / ML

- Baseline: rule-based anomaly detection.
- Nâng cao: Isolation Forest.
- Có thể thêm Local Outlier Factor hoặc One-Class SVM nếu cần.

### LLM Explanation

- Hỗ trợ OpenAI hoặc Claude nếu có API key.
- Nếu không có API key, dùng rule-based explanation để hệ thống vẫn chạy được.

## 8. Vai trò người dùng

### Admin

- Đăng nhập hệ thống.
- Quản lý user.
- Quản lý device.
- Xem toàn bộ dashboard.
- Xem toàn bộ log và alert.
- Đánh dấu trạng thái alert.
- Xem risk score và explanation.

### Analyst

- Đăng nhập hệ thống.
- Xem dashboard.
- Xem danh sách cảnh báo.
- Xem chi tiết anomaly.
- Đọc giải thích từ hệ thống.
- Cập nhật trạng thái xử lý alert.

## 9. Các thành phần cần triển khai

## 9.1. Authentication

Cần có:

- Đăng nhập.
- Đăng xuất.
- JWT token.
- Middleware kiểm tra quyền.
- Seed sẵn tài khoản demo.

Tài khoản demo đề xuất:

```text
Admin:
email: admin@demo.com
password: admin123

Analyst:
email: analyst@demo.com
password: analyst123
```

## 9.2. User Management

Cần có các chức năng:

- Danh sách user.
- Thêm user demo.
- Sửa thông tin user.
- Xóa hoặc khóa user.
- Gán role công việc cho user, ví dụ HR, Accounting, Engineering, Sales.
- Xem risk score hiện tại của từng user.

Thông tin user gợi ý:

```text
id
username
full_name
email
department
job_role
status
created_at
```

## 9.3. Device Management

Vì sản phẩm theo hướng cài agent trên máy công ty cấp, cần quản lý device.

Chức năng:

- Danh sách thiết bị.
- Gán device cho user.
- Xem trạng thái device: online/offline.
- Xem lần cuối agent gửi log.
- Xem risk score của device.
- Xem thông tin hostname, OS, IP.

Thông tin device gợi ý:

```text
id
device_id
hostname
os
ip_address
assigned_user_id
status
last_seen
created_at
```

## 9.4. Endpoint Agent / Mock Agent

Triển khai một agent Python giả lập để demo luồng sản phẩm.

Agent cần làm được:

- Định kỳ sinh event log.
- Gửi log lên backend qua API `POST /api/logs/ingest`.
- Có mode bình thường.
- Có mode bất thường.
- Có thể cấu hình user/device.
- In ra console log đã gửi để dễ demo.

Các event bình thường có thể gồm:

- Đăng nhập trong giờ làm việc.
- Mở file thông thường.
- Truy cập folder đúng quyền.
- Chạy app phổ biến như browser, editor, office.
- Download số lượng file nhỏ.

Các event bất thường cần giả lập:

- Đăng nhập lúc 2-3 giờ sáng.
- Download/copy rất nhiều file trong thời gian ngắn.
- Cắm USB lạ.
- Chạy process đáng ngờ.
- Truy cập folder nhạy cảm ngoài vai trò.
- Đăng nhập từ IP lạ.
- Nhiều lần login fail.

Ví dụ payload agent gửi lên backend:

```json
{
  "user_id": "employee_01",
  "device_id": "laptop_01",
  "timestamp": "2026-06-09T10:30:00",
  "event_type": "file_access",
  "action": "download_file",
  "resource": "/finance/salary_2026.xlsx",
  "resource_sensitivity": "high",
  "ip_address": "192.168.1.20",
  "process_name": "chrome.exe",
  "usb_device": null,
  "bytes_transferred": 10485760,
  "status": "success"
}
```

## 9.5. Log Ingestion

Backend cần có API nhận log từ agent.

API gợi ý:

```text
POST /api/logs/ingest
GET  /api/logs
GET  /api/logs/{id}
GET  /api/users/{user_id}/logs
GET  /api/devices/{device_id}/logs
```

Schema event log gợi ý:

```text
id
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
status
raw_json
created_at
```

Các loại `event_type` gợi ý:

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
```

## 9.6. Feature Extraction

Từ log thô, tạo feature để phục vụ anomaly detection.

Feature gợi ý:

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
```

## 9.7. Anomaly Detection

Cần triển khai ít nhất rule-based anomaly detection để demo dễ hiểu.

Rule gợi ý:

1. Nếu login từ 22:00 đến 06:00 => tăng risk.
2. Nếu truy cập resource sensitivity = high và không đúng department/role => tăng risk.
3. Nếu bytes transferred vượt ngưỡng => tăng risk.
4. Nếu số file truy cập/download trong thời gian ngắn vượt baseline => tăng risk.
5. Nếu process nằm trong danh sách đáng ngờ => tăng risk.
6. Nếu USB device lạ xuất hiện => tăng risk.
7. Nếu nhiều lần login fail => tăng risk.
8. Nếu IP chưa từng thấy với user/device => tăng risk.

Có thể bổ sung Isolation Forest:

- Train bằng mock log bình thường.
- Predict anomaly cho log mới.
- Kết hợp score từ ML với rule score.

## 9.8. Risk Scoring

Risk score nằm trong khoảng 0-100.

Mức độ đề xuất:

```text
0-30: Low
31-60: Medium
61-80: High
81-100: Critical
```

Cách tính đơn giản:

```text
risk_score = rule_score + ml_score_adjustment
```

Ví dụ rule score:

```text
Off-hour login: +20
Sensitive resource access: +25
Role mismatch: +30
Large download: +25
Unknown USB: +35
Suspicious process: +30
Repeated failed login: +20
New IP/device: +15
```

Nếu tổng điểm vượt 100 thì cap về 100.

## 9.9. Alert Management

Khi risk score vượt ngưỡng, hệ thống tạo alert.

Điều kiện tạo alert:

```text
risk_score >= 60
```

Thông tin alert:

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
status
created_at
updated_at
```

Trạng thái alert:

```text
new
investigating
resolved
false_positive
```

API gợi ý:

```text
GET   /api/alerts
GET   /api/alerts/{id}
PATCH /api/alerts/{id}/status
GET   /api/users/{user_id}/alerts
GET   /api/devices/{device_id}/alerts
```

## 9.10. LLM Explanation / Rule-based Explanation

Mỗi alert cần có phần giải thích bằng ngôn ngữ tự nhiên.

Nếu có API key OpenAI/Claude:

- Gửi thông tin log, risk factors và baseline vào LLM.
- LLM trả về explanation ngắn gọn cho analyst.

Nếu không có API key:

- Dùng rule-based explanation fallback.

Ví dụ explanation:

```text
User employee_01 bị đánh dấu rủi ro cao vì đăng nhập lúc 02:13 sáng, truy cập thư mục /finance có độ nhạy cao, tải xuống 320 file trong 10 phút và cắm USB chưa từng xuất hiện trước đó. Hành vi này lệch đáng kể so với baseline bình thường của user.
```

## 10. Admin Dashboard

Dashboard cần có các trang sau.

### 10.1. Login Page

- Form đăng nhập.
- Hiển thị lỗi nếu sai tài khoản/mật khẩu.
- Sau khi đăng nhập chuyển về dashboard.

### 10.2. Overview Dashboard

Hiển thị card tổng quan:

- Tổng số user.
- Tổng số device.
- Số device online.
- Tổng số log hôm nay.
- Tổng số alert.
- Số alert high/critical.
- Top user risk cao nhất.

Biểu đồ cần có:

- Số alert theo thời gian.
- Phân bố severity: Low/Medium/High/Critical.
- Top event type xuất hiện nhiều nhất.
- Top user/device có nhiều cảnh báo.

### 10.3. Users Page

- Bảng danh sách user.
- Search/filter theo department, role, status.
- Hiển thị risk score từng user.
- Bấm vào user để xem chi tiết.

### 10.4. Devices Page

- Bảng danh sách device.
- Trạng thái online/offline.
- User đang được gán.
- Last seen.
- Risk score.
- Bấm vào device để xem log và alert.

### 10.5. Logs Page

- Bảng event log.
- Filter theo user, device, event type, thời gian, severity.
- Xem chi tiết log.

### 10.6. Alerts Page

- Bảng danh sách alert.
- Filter theo severity, status, user, device.
- Màu sắc trực quan theo severity.
- Có nút cập nhật trạng thái alert.

### 10.7. Alert Detail Page

Hiển thị:

- Thông tin user.
- Thông tin device.
- Event log gốc.
- Risk score.
- Các risk factor.
- Explanation.
- Timeline hành vi gần thời điểm alert.
- Nút đổi trạng thái: investigating, resolved, false positive.

### 10.8. User/Device Timeline Page

Hiển thị timeline hành vi:

```text
09:00 - Login success
09:10 - Open normal file
09:20 - Access internal folder
02:13 - Login outside working hours
02:15 - Download 320 sensitive files
02:20 - USB inserted
```

## 1. API endpoint gợi ý

### Auth

```text
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/logout
```

### Users

```text
GET    /api/users
POST   /api/users
GET    /api/users/{id}
PUT    /api/users/{id}
DELETE /api/users/{id}
```

### Devices

```text
GET    /api/devices
POST   /api/devices
GET    /api/devices/{id}
PUT    /api/devices/{id}
DELETE /api/devices/{id}
```

### Logs

```text
POST /api/logs/ingest
GET  /api/logs
GET  /api/logs/{id}
GET  /api/users/{id}/logs
GET  /api/devices/{id}/logs
```

### Alerts

```text
GET   /api/alerts
GET   /api/alerts/{id}
PATCH /api/alerts/{id}/status
GET   /api/users/{id}/alerts
GET   /api/devices/{id}/alerts
```

### Dashboard

```text
GET /api/dashboard/summary
GET /api/dashboard/alerts-over-time
GET /api/dashboard/severity-distribution
GET /api/dashboard/top-risk-users
GET /api/dashboard/top-risk-devices
```

### ML / Analysis

```text
POST /api/analyze/run
POST /api/analyze/log/{log_id}
GET  /api/analyze/baseline/{user_id}
```

## 14. Luồng demo bắt buộc

Cần làm sao để nhóm demo được theo luồng sau:

1. Mở dashboard và đăng nhập bằng tài khoản admin.
2. Xem overview có user, device, log, alert.
3. Chạy agent ở mode bình thường:

```bash
python agent/main.py --mode normal --user employee_01 --device laptop_01
```

4. Dashboard nhận log mới, nhưng không tạo alert nghiêm trọng.
5. Chạy agent ở mode bất thường:

```bash
python agent/main.py --mode anomaly --user employee_01 --device laptop_01
```

6. Agent gửi các event bất thường như off-hour login, large download, unknown USB, suspicious process.
7. Backend tính risk score >= 60 và tạo alert.
8. Dashboard hiển thị alert mới.
9. Admin bấm vào alert detail.
10. Trang detail hiển thị timeline, risk factors và explanation.
11. Admin đổi trạng thái alert sang investigating/resolved.

## 15. Privacy & Compliance note

Vì đây là hệ thống giám sát thiết bị công ty cấp, cần có phần ghi chú về quyền riêng tư trong UI hoặc README:

- Chỉ áp dụng trên thiết bị do công ty cấp.
- Chỉ thu thập metadata/log phục vụ bảo mật.
- Không thu thập mật khẩu.
- Không đọc nội dung tin nhắn cá nhân.
- Không ghi lại nội dung file cá nhân.
- Có thông báo minh bạch cho nhân viên.
- Chỉ admin/analyst có quyền xem cảnh báo.
- Log nhạy cảm cần được giới hạn quyền truy cập.

## 16. Cấu trúc thư mục mong muốn

```text
project-root/
  backend/
    app/
      main.py
      api/
      core/
      models/
      schemas/
      services/
      db/
      seed.py
    requirements.txt
    README.md

  frontend/
    src/
      pages/
      components/
      services/
      hooks/
      utils/
    package.json
    README.md

  agent/
    main.py
    config.py
    event_generator.py
    sender.py
    README.md

  docs/
    architecture.md
    demo_script.md
    privacy_note.md

  README.md
  docker-compose.yml
```

## 17. README cần có

README chính cần hướng dẫn:

- Giới thiệu dự án.
- Kiến trúc hệ thống.
- Tech stack.
- Cách chạy backend.
- Cách chạy frontend.
- Cách chạy agent.
- Cách seed data.
- Tài khoản demo.
- Luồng demo.
- Cách deploy.

## 18. Docker / Deploy

Ưu tiên có Docker để dễ chạy.

Cần có:

```text
docker-compose.yml
backend Dockerfile
frontend Dockerfile nếu cần
.env.example
```

Deploy có thể dùng:

- Backend: Render / Railway / Fly.io
- Frontend: Vercel / Netlify
- Database: SQLite cho demo hoặc PostgreSQL nếu deploy được

## 19. Tiêu chí hoàn thành

Dự án được xem là hoàn thành khi:

- Chạy được backend.
- Chạy được frontend.
- Đăng nhập được.
- Dashboard hiển thị dữ liệu.
- Quản lý được user/device.
- Agent gửi log được về backend.
- Backend phân tích log và tạo alert.
- Risk score hoạt động.
- Alert detail có explanation.
- Có timeline hành vi.
- Có mock data để demo ngay.
- Có README hướng dẫn đầy đủ.
- Có deploy online hoặc hướng dẫn deploy rõ ràng.