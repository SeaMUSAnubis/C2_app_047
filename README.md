# O47 Insider Threat Detection System

Hệ thống phân tích hành vi người dùng và phân tích rủi ro nội bộ (UEBA - User and Entity Behavior Analytics) kết hợp giữa Machine Learning (OCSVM) và Large Language Models (LLMs) để đưa ra giải thích thân thiện cho chuyên gia bảo mật.

## 1. Architecture Diagram
Xem sơ đồ kiến trúc tại file [Architecture Diagram](./artifacts/architecture_diagram.md).

## 2. Setup Instructions

### Yêu cầu hệ thống
- Python 3.10+
- Node.js 18+
- Dữ liệu CERT r4.2 đặt tại `d:\2 Code\TEAM_O47\Data`
- Model weight đặt tại `d:\2 Code\TEAM_O47\Weight`

### Cài đặt Backend
```bash
# 1. Chuyển vào thư mục dự án
cd "d:\2 Code\TEAM_O47\C2-App-047"

# 2. Tạo môi trường ảo (nếu chưa có) và cài đặt dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Khởi chạy FastAPI server
uvicorn src.main:app --reload --port 8000
```

### Cài đặt Frontend
```bash
# 1. Chuyển vào thư mục frontend
cd "d:\2 Code\TEAM_O47\C2-App-047\frontend"

# 2. Cài đặt các gói thư viện
npm install

# 3. Chạy Vite dev server
npm run dev
```

## 3. Environment Variables (Env Vars)

### Backend `.env`
Tạo file `.env` tại thư mục gốc backend:
```env
APP_NAME="O47 UEBA System"
APP_VERSION="1.0.0"
CORS_ORIGINS="http://localhost:5173"
JWT_SECRET="your-secret-key-here"
```

### Frontend `.env`
Tạo file `.env` tại thư mục `frontend`:
```env
VITE_API_BASE_URL=http://localhost:8000/api
```

## 4. Sample Queries
Ví dụ payload JSON gửi tới endpoint `/api/demo/analyze`:
```json
{
  "user_id": "HSB0196",
  "events": [
    {
      "event_type": "logon",
      "timestamp": "2010-01-02T09:00:00Z",
      "pc": "PC-8001"
    },
    {
      "event_type": "file",
      "timestamp": "2010-01-02T09:49:30Z",
      "filename": "RJGC8XX5.exe"
    }
  ]
}
```

## 5. Eval Evidences
Bạn có thể tham khảo kết quả phân tích 5 kịch bản thực tế (lấy từ log của tập CERT) tại báo cáo [Eval Evidences](./artifacts/eval_evidences.md).
Mọi cảnh báo đều được Model nhận diện dựa trên baseline của user, từ đó LLM sẽ tổng hợp ra một câu giải thích bằng ngôn ngữ tự nhiên.
