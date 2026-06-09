# BRIEF

# HỆ THỐNG PHÁT HIỆN BẤT THƯỜNG HÀNH VI NGƯỜI DÙNG & TÀI KHOẢN

## 1. Tại sao làm sản phẩm này? (Bối cảnh & Vấn đề)

Các mối đe dọa an ninh thông tin từ **tài khoản bị chiếm quyền (compromised accounts)** và **nhân viên nội gián (insider threats)** ngày càng tinh vi. Họ thường có hành vi lệch chuẩn như: đăng nhập giờ lạ, truy cập dữ liệu trái thẩm quyền, hoặc tải file dung lượng lớn đột biến.

### Thực trạng & Nỗi đau (Pain points)

- **Dữ liệu phân mảnh:** Các tín hiệu cảnh báo nằm rải rác, cô lập trong hàng Gigabyte dữ liệu log hệ thống mỗi ngày.
- **Thiếu "Baseline" (Hành vi chuẩn):** Đội ngũ bảo mật không có công cụ để định nghĩa thế nào là "hành vi bình thường" của từng nhân viên hoặc tài khoản dịch vụ để làm căn cứ so sánh.
- **Quá tải cảnh báo (Alert Fatigue):** Các hệ thống cũ chỉ trả ra các con số hoặc cảnh báo thô, khiến chuyên viên phân tích (Analyst) mất quá nhiều thời gian để xâu chuỗi và điều tra.

## 2. Làm cho ai? (Đối tượng mục tiêu)

- **Người dùng trực tiếp (End-users):** Đội ngũ An ninh thông tin (Cybersecurity Analysts), Quản trị viên hệ thống (SysAdmin) tại các doanh nghiệp.
- **Đối tượng quản lý/giám sát:** Ban giám đốc, bộ phận Quản trị rủi ro & Tuân thủ (Risk & Compliance).
- **Đối tượng bị tác động ngầm:** Toàn bộ nhân viên và các tài khoản dịch vụ trong tổ chức (hệ thống chạy ngầm để bảo vệ tài sản doanh nghiệp nhưng cần đảm bảo quyền riêng tư).

## 3. Mục tiêu sản phẩm (Objectives)

- **Xây dựng Baseline tự động:** Dùng AI học hành vi chuẩn từ log truy cập của từng cá nhân/tài khoản.
- **Phát hiện và Chấm điểm rủi ro:** Tự động phát hiện các hành vi lệch chuẩn (leo thang quyền, bất khả thi về địa lý, truy cập vùng nhạy cảm) và gán điểm số ưu tiên điều tra.
- **Diễn giải thông minh bằng LLM:** Chuyển đổi các con số khô khan và log thô thành báo cáo tóm tắt bằng ngôn ngữ tự nhiên để Analyst hiểu ngay lập tức.
- **Tối ưu vận hành:** Giúp doanh nghiệp chủ động ngăn chặn lộ lọt dữ liệu trước khi hậu quả nghiêm trọng xảy ra, đồng thời cân bằng giữa giám sát và quyền riêng tư của nhân viên.

## 4. Phạm vi sản phẩm (Scope)

### Thuộc phạm vi (In-Scope) - MVP Phải có

- **Hệ thống Web App hoàn chỉnh:** Có giao diện UI/UX trực quan (Dashboard), quản lý user và phân quyền cơ bản. Được deploy online (có URL truy cập công khai).
- **Log Ingestion & AI Engine:** Module tiếp nhận dữ liệu log, xử lý mô hình Time-series Anomaly Detection để tìm điểm bất thường và chấm điểm rủi ro.
- **Module LLM Diễn giải:** Tích hợp OpenAI/Claude API để "dịch" các cảnh báo kỹ thuật thành văn bản giải thích ngữ cảnh cho Analyst.
- **Trực quan hóa:** Giao diện hiển thị danh sách cảnh báo, biểu đồ xu hướng rủi ro và thứ tự ưu tiên điều tra.

### Ngoài phạm vi (Out-of-Scope) - Không làm ở giai đoạn này

- Hệ thống tự động ngăn chặn/khóa tài khoản theo thời gian thực (Active Blocking/SOAR).
- Xử lý tất cả các loại log trên đời (Giai đoạn đầu chỉ tập trung vào log truy cập hệ thống/dữ liệu cốt lõi).

## Tóm tắt nhanh

| Trọng tâm | Ý nghĩa |
|---|---|
| Why | Phát hiện hành vi lệch chuẩn từ log, giảm quá tải cảnh báo và hỗ trợ điều tra nhanh. |
| Who | Cybersecurity Analysts, SysAdmin, Risk & Compliance, Ban giám đốc và toàn bộ tài khoản trong tổ chức. |
| MVP | Web app deploy online, ingestion log, AI anomaly detection, risk scoring, LLM explanation, dashboard trực quan. |
