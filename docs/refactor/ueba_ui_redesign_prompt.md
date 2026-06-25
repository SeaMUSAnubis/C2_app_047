# UEBA Frontend UI Redesign Prompt

## Mục tiêu

Refactor lại giao diện frontend của project UEBA thành một dashboard hiện đại theo phong cách SOC/SIEM cybersecurity dashboard.

Project hiện tại là:

- UEBA / User & Entity Behavior Analytics
- Theo dõi user, device, logs, alerts
- Phát hiện anomaly
- Tính risk score
- Có phần ML/model riêng, không được đụng vào

UI hiện tại đang quá đơn giản, nhiều khoảng trống, chart placeholder, thiếu cảm giác security product. Cần code lại UI frontend cho đẹp, chuyên nghiệp, dễ demo.

---

## Inspiration UI

Không copy y nguyên bất kỳ sản phẩm nào, chỉ lấy cảm hứng từ các dashboard security/SOC/SIEM sau:

1. Datadog Cloud SIEM
2. Microsoft Sentinel UEBA
3. Splunk Enterprise Security
4. Elastic Security
5. CrowdStrike Falcon
6. Dribbble/Behance cybersecurity dashboards

---

## Ràng buộc quan trọng

- Tất cả source code phải nằm trong `src/`.
- Frontend nằm trong `src/frontend/`.
- Không sửa ML/model/weights.
- Không sửa backend nếu không cần.
- Không xóa dữ liệu.
- Không commit.
- Không push.
- Không tạo source code ở ngoài `src/`.
- Không để chart placeholder.
- Không phá route `/dashboard`.
- Không dùng UI library quá nặng nếu không cần.

---

## Tech stack

Frontend dùng:

- React
- Vite
- TypeScript

Có thể dùng thêm:

- `lucide-react` cho icon
- `recharts` cho chart

Nếu thiếu dependency thì cập nhật `src/frontend/package.json`.

---

## Style direction

Thiết kế UI theo style:

- Modern dark cybersecurity dashboard
- SOC analyst console
- SIEM/security monitoring
- UEBA endpoint monitoring
- Real-time anomaly/risk dashboard

Màu sắc gợi ý:

```css
:root {
  --bg: #07111f;
  --bg-soft: #0b1628;
  --surface: #101d31;
  --surface-2: #14243a;
  --border: rgba(148, 163, 184, 0.18);
  --text: #e5f0ff;
  --muted: #8ea3bd;
  --primary: #38bdf8;
  --primary-2: #2563eb;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
  --critical: #fb1746;
}
```

Yêu cầu visual:

- Dark navy background
- Card có border subtle
- Có glow nhẹ cho active state
- Accent cyan/electric blue
- Critical alert dùng đỏ
- High alert dùng cam/đỏ
- Medium dùng vàng
- Low dùng xanh
- Không lạm dụng gradient
- Không để dashboard trống quá nhiều
- Font clean, readable
- Spacing gọn
- Responsive tốt ở màn 1366px trở lên

---

## Cấu trúc frontend mong muốn

Kiểm tra frontend hiện tại trong `src/frontend/`, sau đó refactor theo cấu trúc sau nếu phù hợp:

```text
src/frontend/src/
├── App.tsx
├── main.tsx
├── api/
│   └── client.ts
├── components/
│   ├── AppShell.tsx
│   ├── Sidebar.tsx
│   ├── Topbar.tsx
│   ├── StatCard.tsx
│   ├── SeverityBadge.tsx
│   ├── RiskScore.tsx
│   ├── ChartCard.tsx
│   ├── AlertItem.tsx
│   ├── DataTable.tsx
│   └── EntityCard.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── Alerts.tsx
│   ├── Users.tsx
│   ├── Devices.tsx
│   ├── Logs.tsx
│   └── ModelTest.tsx
├── data/
│   └── mockData.ts
└── styles/
    └── global.css
```

Nếu project đã có file tương tự, hãy sửa/refactor lại thay vì tạo file trùng lặp lung tung.

---

## App shell

Tạo layout chung cho toàn app.

### Sidebar

Sidebar cần có:

- Logo/tên project: `Vespionage`
- Subtitle nhỏ: `UEBA Console`
- Menu:
  - Dashboard
  - Alerts
  - Users
  - Devices
  - Logs
  - Model Test
- Active state rõ
- Icon cho từng menu
- Hover đẹp
- Không chiếm quá nhiều diện tích

### Topbar

Topbar cần có:

- Global search input
- Badge `Live`
- Badge environment `Demo`
- Time range text, ví dụ `Last 24h`
- Admin profile
- Nút hoặc icon notification

---

## Dashboard page

Trang Dashboard phải đẹp và đầy dữ liệu, không để trống.

Route cần giữ:

```text
/dashboard
```

Dashboard gồm các section:

### 1. Header summary

Nội dung:

- Title: `UEBA Security Operations`
- Subtitle: `Monitor user and entity behavior anomalies across endpoints, logs, and access patterns.`
- Time range selector mock:
  - Last 24h
  - 7d
  - 30d
- Button: `Run Analysis`

### 2. KPI cards

Hiển thị ít nhất 6 KPI:

- Total Users
- Monitored Devices
- Events Processed
- Active Alerts
- High Risk Users
- Avg Risk Score

Mỗi KPI card có:

- Icon
- Label
- Value
- Delta nhỏ, ví dụ `+12.4%`
- Tone màu riêng

### 3. Risk overview

Có chart thật bằng mock data, không dùng placeholder.

Cần có ít nhất:

- Line chart: Risk trend over time
- Bar chart: Alert volume by severity
- Donut/Pie chart hoặc stacked bar: Risk distribution

### 4. Recent critical alerts

Mỗi alert hiển thị:

- Title
- User
- Device
- Severity
- Risk score
- Timestamp
- Short explanation

Ví dụ alert:

- `Off-hours access outside baseline`
- `Multiple failed logins followed by large data transfer`
- `Impossible travel detected`
- `Privilege escalation attempt`
- `Bulk download from sensitive repository`

### 5. Top risky entities

Hiển thị bảng/card gồm:

- User/device
- Role
- Department
- Device
- Last activity
- Anomaly type
- Risk score

### 6. Activity timeline

Timeline gồm các event:

- Login anomaly
- Off-hours access
- Bulk download
- Failed login spike
- Impossible travel
- Privilege escalation
- New device login
- Blocked website access

---

## Alerts page

Trang Alerts cần giống SOC alert queue.

Cần có:

### Filter bar

- Search input
- Severity filter
- Status filter
- Entity filter
- Date range mock

### Alert table

Columns:

- Alert
- Entity
- Device
- Severity
- Risk score
- Status
- Time
- Action

### Alert detail panel hoặc detail card

Hiển thị:

- Alert explanation
- Evidence
- Recommended action
- MITRE-like tag mock
- Related events

---

## Users page

Trang Users cần giống UEBA entity analytics.

Cần có:

- User table/list
- Risk score
- Role
- Department
- Device count
- Last seen
- Baseline status
- Anomaly count

Khi chọn user hoặc ở panel bên phải, hiển thị profile card:

- User baseline
- Normal login hours
- Common devices
- Recent anomalies
- Risk explanation

---

## Devices page

Trang Devices cần có:

- Device inventory
- Device risk level
- Owner
- OS
- Last IP
- Last seen
- Suspicious events count
- Device posture/status

---

## Logs page

Trang Logs cần giống SIEM log search.

Cần có:

### Search/filter

- Search input
- Event type filter
- Severity filter
- Date range mock
- Result/status filter

### Log table

Columns:

- Timestamp
- User
- Device
- Event Type
- Source IP
- Resource
- Result
- Risk Score

Yêu cầu:

- Table đọc rõ
- Row hover đẹp
- Severity/risk có màu
- Có mock pagination hoặc summary count

---

## ModelTest page

Trang test model ML.

Cần có form nhập mock event:

- user_id
- device_id
- event_type
- hour
- source_ip
- resource
- action_count

Có button:

```text
Predict Risk
```

Result card hiển thị:

- anomaly score
- risk score
- severity
- explanation

Nếu backend chưa sẵn sàng, dùng mock result nhưng code phải tách rõ để sau này nối API.

---

## Mock data

Tạo file:

```text
src/frontend/src/data/mockData.ts
```

Mock data phải realistic cho UEBA.

Users mẫu:

- Nguyen Van A
- Tran Thi B
- Pham Minh C
- Le Hoang D
- Do Anh E

Event types:

- off_hours_login
- bulk_download
- failed_login_spike
- unusual_location
- privilege_escalation
- blocked_website_access
- impossible_travel
- new_device_login

Severity:

- low
- medium
- high
- critical

Status:

- open
- investigating
- resolved
- false_positive

Risk score từ 0 đến 100.

---

## API integration

Tạo hoặc cập nhật:

```text
src/frontend/src/api/client.ts
```

Dùng env:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Nếu backend chưa đầy đủ, frontend vẫn chạy bằng mock data.

Không hard-code backend URL trực tiếp trong component.

---

## Implementation steps

Làm theo thứ tự:

1. Inspect cấu trúc hiện tại trong `src/frontend`.
2. Lập danh sách file sẽ sửa/tạo.
3. Tạo/cập nhật global styles.
4. Tạo mock data.
5. Tạo/refactor AppShell, Sidebar, Topbar.
6. Tạo/refactor components dùng chung.
7. Code lại Dashboard.
8. Code lại Alerts.
9. Code lại Users.
10. Code lại Devices.
11. Code lại Logs.
12. Code lại ModelTest.
13. Cập nhật routing/navigation.
14. Cài dependency nếu cần.
15. Chạy build frontend.
16. Sửa lỗi TypeScript/build nếu có.
17. Báo cáo lại kết quả.

---

## Test commands

Sau khi code xong, chạy:

```bash
cd src/frontend
npm install
npm run build
```

Nếu có lint thì chạy thêm:

```bash
npm run lint
```

Nếu build lỗi thì phải sửa đến khi build pass, trừ khi lỗi do dependency/network ngoài tầm kiểm soát.

---

## Không được làm

- Không sửa ML logic.
- Không xóa ML weights/model artifacts.
- Không train model.
- Không sửa database nếu không cần.
- Không sửa backend nếu không cần.
- Không commit.
- Không push.
- Không tạo source code ngoài `src/`.
- Không để chart placeholder.
- Không để page trống.
- Không phá route hiện tại.
- Không copy y nguyên UI của sản phẩm thật.

---

## Quality checklist

Trước khi báo xong, tự kiểm tra:

- Dashboard không còn chart placeholder.
- Có ít nhất 3 chart thật dùng mock data.
- Có đầy đủ page Dashboard, Alerts, Users, Devices, Logs, Model Test.
- Sidebar điều hướng được.
- Topbar đẹp và có trạng thái Live/Demo.
- UI có cảm giác SOC/SIEM cybersecurity dashboard.
- Card/table/alert có hierarchy rõ.
- Critical alert nổi bật.
- Risk score dễ nhìn.
- Màu sắc nhất quán.
- Build frontend pass.
- Không đụng vào ML/weights.

---

## Final report format

Sau khi hoàn thành, báo cáo theo format:

```md
# UI Refactor Summary

## Changed files
- ...

## New components
- ...

## New pages
- ...

## Mock data added
- ...

## Dependencies added
- ...

## Build result
- ...

## Notes
- ...
```
