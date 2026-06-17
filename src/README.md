# Vespionage - Hướng dẫn sử dụng & Cấu trúc mã nguồn

**Vespionage** là một hệ thống phân tích hành vi người dùng và thực thể (UEBA - User and Entity Behavior Analytics) được thiết kế với giao diện cao cấp (Premium Glassmorphism UI) và tích hợp trí tuệ nhân tạo (LLM qua OpenRouter) để hỗ trợ các chuyên gia bảo mật (SOC Analysts) phát hiện, điều tra và phản hồi các mối đe dọa an ninh.

---

## 1. Cấu trúc thư mục dự án

Toàn bộ dự án đã được tối ưu hóa và gom gọn vào thư mục `src/` nhằm mang lại sự đồng nhất:

```text
C2-App-047/
├── src/
│   ├── frontend/         # Giao diện người dùng (React, Vite, Vanilla CSS cao cấp)
│   ├── scripts/          # Công cụ kịch bản (Nạp dữ liệu, Đánh giá LLM, Quản lý Database)
│   ├── api/              # Các API Endpoints của Backend (FastAPI routes)
│   ├── models/           # Cấu trúc DB (SQLAlchemy) và DTO (Pydantic)
│   ├── services/         # Xử lý nghiệp vụ: Database, Logic LLM, Machine Learning Pipelines
│   ├── agents/           # Các Sub-Agent AI tự động (nếu có)
│   ├── config.py         # Trình quản lý cấu hình môi trường (.env)
│   ├── main.py           # Điểm khởi chạy của Backend Server
│   └── README.md         # Hướng dẫn sử dụng (File bạn đang đọc)
├── .venv/                # Môi trường ảo Python
├── .env                  # Chứa các thông tin nhạy cảm (API Keys, Database URL)
├── requirements.txt      # Danh sách thư viện Python
└── docker-compose.yml    # Cấu hình Docker
```

---

## 2. Hướng dẫn Khởi động Hệ thống

Hệ thống hoạt động dựa trên sự giao tiếp giữa **Backend (FastAPI)** và **Frontend (React)**. Bạn cần mở **2 cửa sổ Terminal** riêng biệt.

### A. Khởi động Backend (FastAPI)

1. Mở Terminal (PowerShell / CMD) tại thư mục gốc `C2-App-047`.
2. Kích hoạt môi trường ảo:
   ```bash
   .\.venv\Scripts\activate
   ```
4. Khởi động Server Backend (chú ý đường dẫn trỏ vào `src.main:app`):
   ```bash
   uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *Backend sẽ chạy tại địa chỉ: `http://127.0.0.1:8000`*

### Bước 2: Khởi động Frontend Server (Cổng 5173)

1. Mở Terminal MỚI tại thư mục gốc `C2-App-047`.
2. Di chuyển vào thư mục Frontend:
   ```bash
   cd src\frontend
   ```
3. Chạy lệnh khởi động giao diện Web:
   ```bash
   npm run dev
   ```
   > Giao diện sẽ hiển thị tại: `http://localhost:5173`

---

## 🕵️ Hướng dẫn sử dụng Dashboard Web

Truy cập `http://localhost:5173` trên trình duyệt.

### 1. Đăng nhập
- **Tài khoản Admin:** `admin@demo.com` / `admin123`
- **Tài khoản Analyst:** `analyst@demo.com` / `analyst123`

### 2. Các chức năng chính
- **Overview:** Bảng điều khiển tổng quan về sức khỏe hệ thống.
- **Alerts:** Danh sách các cảnh báo bất thường được phát hiện bởi thuật toán AI (`One-Class SVM`).
- **Users / Devices:** Thông tin chi tiết của từng người dùng và thiết bị (Đã được nạp từ tập dữ liệu thực tế CERT r4.2).
- **Data Import:** Quản lý dữ liệu, cho phép bạn kích hoạt thuật toán AI phân tích lại toàn bộ log.

### 3. Khắc phục lỗi "Import failed" hoặc "Unauthorized"
Nếu bạn gặp thông báo lỗi màu đỏ khi bấm nút, nguyên nhân thường là do phiên làm việc (Session Token) đã hết hạn.
👉 **Cách xử lý:** Bấm nút **Logout** góc trên bên phải, sau đó **Login** lại.

---

## Tích hợp Trí tuệ Nhân tạo (OpenRouter LLM)

Vespionage sử dụng API của **OpenRouter** để đưa ra các lời giải thích cực kỳ sắc bén (AI Explainer) cho từng cảnh báo rủi ro. Tính năng này được cài đặt mặc định để yêu cầu AI **trả lời 100% bằng tiếng Việt**.

### Đổi Mô hình (Model) AI:
Bạn có thể dễ dàng thay đổi bộ não AI bằng cách mở file `.env` ở thư mục gốc và sửa đổi biến:
```env
OPENROUTER_MODEL=openrouter/free
```
*Gợi ý một số model phổ biến:*
- `openrouter/free`: Tự động chọn Model miễn phí tốt nhất tại thời điểm truy vấn.
- `google/gemini-2.5-flash`: Tốc độ cực nhanh, giá rẻ.
- `openai/gpt-4o-mini`: Tư duy sắc bén, phản hồi ổn định.

---

## 🛠️ Quản lý Dữ liệu bằng Script

Tất cả các Script tiện ích đều nằm ở `src\scripts`. Chạy các file này từ Terminal **đã kích hoạt `.venv`** tại thư mục gốc `C2-App-047`.

**1. Nạp dữ liệu thực tế (CERT r4.2 Dataset)**
Nếu Database bị trống, bạn có thể nạp lại toàn bộ file CSV thực tế vào hệ thống:
```bash
python src\scripts\seed_mock_data.py
```

**2. Làm sạch Database (Tùy chọn nâng cao)**
Nếu bạn muốn xóa toàn bộ Cảnh báo (Alerts) hiện tại để chạy test lại từ đầu, bạn có thể dùng một file script như `clear_alerts.py` (nếu có) hoặc gọi hàm `TRUNCATE TABLE alerts` thông qua dịch vụ Database.

**3. Đánh giá LLM**
Test khả năng phản hồi của LLM:
```bash
python src\scripts\evaluate_llm.py
```
