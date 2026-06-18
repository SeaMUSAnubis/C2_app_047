# Vespionage UEBA Dashboard

Chào mừng đến với dự án giao diện người dùng (UI shell) của **Vespionage UEBA Endpoint Monitoring**. Đây là một Dashboard giám sát hành vi người dùng và thiết bị dựa trên nền tảng React, TypeScript và Vite.

Dự án hiện tại cung cấp bộ khung giao diện với dữ liệu mẫu (mock data), cho phép người dùng thao tác, điều hướng và quan sát cách hệ thống phân tích và quản lý rủi ro trên các thiết bị cuối.

## Danh sách các trang

Các trang trong hệ thống được thiết kế để tạo nên một luồng giám sát an ninh (analyst workflow) hoàn chỉnh:

### 1. Login Page (`/login`)
- **Lý do có:** Là lớp bảo mật đầu tiên, đảm bảo chỉ những người có quyền (Admin, Analyst) mới có thể truy cập vào dữ liệu nhạy cảm của tổ chức.
- **Tính năng:** Cung cấp form đăng nhập, xác thực người dùng. Hiện tại đang hỗ trợ các tài khoản demo (như admin/analyst).

### 2. Dashboard / Overview (`/dashboard`)
- **Lý do có:** Là "trung tâm điều khiển" cung cấp cái nhìn tổng quan toàn diện và nhanh nhất về tình trạng an ninh của toàn bộ hệ thống ngay khi đăng nhập.
- **Tính năng:** Hiển thị các chỉ số quan trọng (KPIs) như tổng số user, thiết bị, lượng logs thu thập, các cảnh báo nguy hiểm (High/Critical Alerts), và điểm rủi ro trung bình.

### 3. Users Page (`/users`)
- **Lý do có:** Trong hệ thống UEBA (User and Entity Behavior Analytics), người dùng là đối tượng trung tâm có khả năng gây ra rủi ro (do vô tình hoặc cố ý). Trang này giúp theo dõi và quản lý tập trung toàn bộ tài khoản.
- **Tính năng:** Danh sách toàn bộ người dùng, điểm rủi ro (Risk Score) của từng người, tình trạng hoạt động, thiết bị đang sử dụng, phòng ban, và tìm kiếm cơ bản.

### 4. Devices Page (`/devices`)
- **Lý do có:** Thiết bị cuối (Endpoint) là nơi các cuộc tấn công hoặc rò rỉ dữ liệu thường xảy ra nhất. Việc giám sát tình trạng thiết bị song song với người dùng là vô cùng cần thiết.
- **Tính năng:** Hiển thị danh sách thiết bị (PC, Laptop), ai đang sử dụng, điểm rủi ro của thiết bị, số cảnh báo đang mở và thời gian hoạt động gần nhất.

### 5. Event Logs Page (`/logs`)
- **Lý do có:** Đây là nền tảng dữ liệu gốc chứng minh các điểm số rủi ro (Risk Score) không phải được tạo ra ngẫu nhiên. Các log ghi lại toàn bộ hoạt động của hệ thống là bằng chứng để các nhà phân tích (analyst) tiến hành điều tra.
- **Tính năng:** Bảng dữ liệu log chuyên sâu với thời gian, loại sự kiện (logon, file, http,...), người dùng/thiết bị liên quan và chi tiết hành động.

*(Các trang như Alerts, Data Import, ML Models, Settings đang được quy hoạch và sẽ hoàn thiện ở các Sprint tiếp theo)*

---

## Hướng dẫn sử dụng và Cài đặt

### Yêu cầu hệ thống
- Node.js (phiên bản 18+ khuyến nghị)
- npm hoặc yarn

### Cài đặt
1. Mở Terminal (Command Prompt / PowerShell) và trỏ vào thư mục `frontend`:
   ```bash
   cd C2-App-047\frontend
   ```
2. Cài đặt các gói thư viện cần thiết:
   ```bash
   npm install
   ```

### Chạy ứng dụng trên máy cá nhân
1. Khởi động môi trường phát triển (Dev server):
   ```bash
   npm run dev
   ```
2. Mở trình duyệt và truy cập vào đường dẫn:
   **http://localhost:5173/**

### Tài khoản Demo (để test đăng nhập)
Để vượt qua màn hình Login và trải nghiệm Dashboard, bạn có thể sử dụng các email sau (mật khẩu nhập bất kỳ):
- Dành cho quyền Quản trị: `admin@demo.com`
- Dành cho quyền Phân tích viên: `analyst@demo.com`

---
*Dự án hiện đang sử dụng dữ liệu mẫu (Mock Data). Trong tương lai, hệ thống sẽ kết nối với Backend API thực tế thông qua biến môi trường `VITE_API_BASE_URL`.*
