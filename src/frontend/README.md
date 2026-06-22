# Giao diện dashboard Vespionage UEBA

## 1. Tổng quan sản phẩm

Đây là frontend dashboard cho hệ thống Vespionage / UEBA Endpoint Monitoring. Giao diện hiển thị người dùng, thiết bị, log đã chuẩn hóa, cảnh báo bất thường, điểm rủi ro, timeline, phần giải thích và thao tác quản trị danh sách website bị chặn.

## 2. Vai trò người dùng

- **Admin**: toàn quyền — xem mọi trang, quản account, model, dataset, blocked websites (thêm/sửa/xóa).
- **Quản lý bảo mật (security_manager)**: xem toàn bộ alerts/users/devices/logs, đổi status alert, ingest data, chạy phân tích toàn bộ, quản lý website bị chặn (thêm/sửa, không xóa). Không quản account/user-device CRUD.
- **Phân tích viên (analyst)**: xem/đổi status alert, xem users/devices/logs, ingest log đơn lẻ, thử ML. Không chạy phân tích toàn bộ, không import dataset, không quản blocked websites.
- **Nhân viên (employee)**: chỉ xem hồ sơ rủi ro cá nhân (`/my-risk`) + kiểm thử ML. Không thấy dữ liệu của người khác.

## 3. Trang và route

- `/login`: trang đăng nhập.
- `/dashboard`: chỉ số tổng quan và phân bố rủi ro (admin/security_manager/analyst).
- `/alerts`: danh sách cảnh báo có filter (admin/security_manager/analyst).
- `/users`: danh sách người dùng và điểm rủi ro (admin/security_manager/analyst).
- `/devices`: danh sách thiết bị và điểm rủi ro (admin/security_manager/analyst).
- `/logs`: log endpoint đã chuẩn hóa (admin/security_manager/analyst).
- `/model-test`: kiểm thử suy luận ML (mọi role).
- `/my-risk`: hồ sơ rủi ro cá nhân (employee, các role khác cũng xem được).
- `/admin/blocked-websites`: quản trị website bị chặn (admin/security_manager).
- `/admin/accounts`: quản trị tài khoản hệ thống (admin).

## 4. Biến môi trường

Khi chạy frontend bằng Vite local, tạo file `.env` trong `src/frontend/`:

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_USE_MOCKS=true
```

Khi chạy Docker một container ở root project, frontend được build với:

```env
VITE_API_BASE_URL=/api
```

## 5. Cách chạy local

```bash
cd src/frontend
npm install
npm run dev
```

## 6. Tài khoản demo

Khi `VITE_USE_MOCKS=true`, có thể dùng tài khoản mock sau:

```text
Admin:            admin@demo.com / admin123
Security Manager: security@demo.com / security123
Analyst:          analyst@demo.com / analyst123
Employee:         employee@demo.com / employee123
```

## 7. Hợp đồng API backend

```http
POST /api/auth/login
GET /api/auth/me

GET /api/dashboard/summary
GET /api/dashboard/risk-distribution
GET /api/dashboard/recent-alerts
GET /api/dashboard/top-risk-users
GET /api/dashboard/top-suspicious-domains
GET /api/dashboard/event-volume

GET /api/alerts
GET /api/alerts/:id
GET /api/alerts/:id/timeline
GET /api/alerts/:id/explanation
PATCH /api/alerts/:id/status

GET /api/users
GET /api/users/:id
GET /api/users/:id/logs
GET /api/users/:id/alerts
GET /api/users/:id/devices

GET /api/devices
GET /api/devices/:id
GET /api/devices/:id/logs
GET /api/devices/:id/alerts

GET /api/logs

GET /api/admin/blocked-websites
POST /api/admin/blocked-websites
PATCH /api/admin/blocked-websites/:id
DELETE /api/admin/blocked-websites/:id
```

## 8. Schema response dự kiến

**Login Response:**

```json
{
  "access_token": "demo-token",
  "token_type": "bearer",
  "user": {
    "id": "acc_admin",
    "email": "admin@demo.com",
    "name": "Demo Admin",
    "role": "admin"
  }
}
```

**Dashboard Summary:**

```json
{
  "total_users": 120,
  "total_devices": 86,
  "total_logs": 245000,
  "active_alerts": 14,
  "high_risk_users": 6,
  "critical_alerts": 2,
  "blocked_websites": 5
}
```

**Alert Explanation:**

```json
{
  "alert_id": "ALERT-1021",
  "summary": "Người dùng có truy cập web bên ngoài bất thường ngoài giờ làm việc.",
  "why_suspicious": [
    "Hoạt động xảy ra ngoài baseline lịch sử của người dùng.",
    "Người dùng truy cập nhiều domain ngoài trong thời gian ngắn."
  ],
  "evidence": [
    "Điểm rủi ro là 87/100.",
    "Feature bất thường nổi bật: after_hours_http_count."
  ],
  "baseline_comparison": "Người dùng thường có mức HTTP activity thấp ngoài giờ làm việc.",
  "recommended_action": [
    "Xem lại timeline.",
    "Kiểm tra domain có phục vụ công việc hay không.",
    "Escalate hoặc block domain nếu xác nhận đáng ngờ."
  ],
  "generated_by": "rule_based"
}
```

## 9. Mock mode

- Khi backend chưa chạy, frontend có thể dùng mock data với `VITE_USE_MOCKS=true`.
- Khi backend sẵn sàng, đổi env để gọi API thật.
- Không cần sửa component khi chuyển từ mock sang API thật.

## 10. Ghi chú tích hợp backend

- JWT auth trả về role.
- Admin-only endpoint dùng cho blocked websites.
- Alert endpoint có `suspicious_urls`.
- Alert detail có timeline.
- Explanation có thể đến từ LLM hoặc fallback rule-based.
- Risk score luôn nằm trong khoảng 0-100.
- Severity enum thống nhất: `low`, `medium`, `high`, `critical`.
- Status enum thống nhất: `new`, `investigating`, `resolved`, `false_positive`.

## 11. Ghi chú riêng tư

Dashboard chỉ dùng cho demo/security monitoring. Giao diện chỉ nên hiển thị metadata bảo mật endpoint và tránh lộ nội dung cá nhân nhạy cảm.
