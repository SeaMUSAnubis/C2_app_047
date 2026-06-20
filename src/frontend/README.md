# Vespionage UEBA Frontend Dashboard

## 1. Product Overview

Frontend dashboard for Vespionage / UEBA Endpoint Monitoring.
It visualizes users, devices, normalized logs, anomaly alerts, risk scores, timelines, explanations, and admin website blocklist actions.

## 2. Roles

* **Analyst**: Can view dashboards, investigate alerts, view users/devices/logs, and see explanations. Analyst can only view or suggest/request block action.
* **Admin**: Has all Analyst capabilities. In addition, **Admin can add suspicious URLs/domains to the blocked websites list.**

## 3. Pages and routes

* `/login` - Authentication page
* `/dashboard` - High-level metrics and risk distribution
* `/alerts` - Alert list with filters
* `/alerts/:id` - Deep dive into an alert (Timeline, Explanation, Actions)
* `/users` - User list and risk scores
* `/users/:id` - User profile and activity
* `/devices` - Device list and risk scores
* `/devices/:id` - Device details
* `/logs` - Raw normalized endpoint logs
* `/admin/blocked-websites` - Admin-only interface to manage blocklist

## 4. Environment variables

Create a `.env` file in the `frontend` directory:
```
VITE_API_BASE_URL=http://localhost:8000/api
VITE_USE_MOCKS=true
```

## 5. How to run

```bash
cd src/frontend
npm install
npm run dev
```

## 6. Demo accounts

When `VITE_USE_MOCKS=true`, you can use the following mock accounts:
```
Admin:
email: admin@demo.com
password: password123

Analyst:
email: analyst@demo.com
password: password123
```

## 7. API contract for backend

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

## 8. Expected response schemas

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
  "summary": "The user showed abnormal external web access outside normal working hours.",
  "why_suspicious": [
    "The activity happened outside the user's historical baseline.",
    "The user accessed multiple external domains in a short time window."
  ],
  "evidence": [
    "Risk score is 87/100.",
    "Top anomalous feature: after_hours_http_count."
  ],
  "baseline_comparison": "The user normally has low HTTP activity after working hours.",
  "recommended_action": [
    "Review the timeline.",
    "Check whether the domain is business-related.",
    "Escalate or block the domain if confirmed suspicious."
  ],
  "generated_by": "rule_based"
}
```

## 9. Mock mode

* Khi backend chưa chạy, frontend dùng mock data (`VITE_USE_MOCKS=true`).
* Khi backend sẵn sàng, set env để gọi API thật.
* Không sửa component khi chuyển mock sang API thật.

## 10. Backend integration notes

* JWT auth trả về role
* Admin-only endpoint cho blocked websites
* Alert endpoint có suspicious_urls
* Alert detail có timeline
* Explanation có thể là LLM hoặc rule_based fallback
* Risk score luôn trong khoảng 0-100
* Severity enum thống nhất: low/medium/high/critical
* Status enum thống nhất: new/investigating/resolved/false_positive

## 11. Privacy note

This dashboard is for demo/security monitoring purposes. It should display endpoint security metadata only and avoid exposing sensitive personal content.
