# Sơ đồ kiến trúc hệ thống UEBA

Tài liệu này mô tả các thành phần đang được triển khai và luồng dữ liệu chính của hệ thống phát hiện nguy cơ nội bộ dựa trên CERT r4.2, OCSVM và LLM.

## 1. Sơ đồ thành phần

```mermaid
flowchart LR
    analyst["SOC Analyst / Admin"]
    sources["Nguồn dữ liệu<br/>CERT r4.2 CSV / Endpoint events"]
    openrouter["OpenRouter API<br/>LLM bên ngoài"]

    subgraph frontend["Frontend - React + Vite"]
        pages["Trang nghiệp vụ<br/>Dashboard, Alerts, Users,<br/>Devices, Logs, Data Import"]
        client["API Client"]
        session["JWT + thông tin người dùng<br/>localStorage"]
        pages --> client
        session --> client
    end

    subgraph backend["Backend - FastAPI"]
        routes["REST API /api<br/>Auth, Dashboard, Entities,<br/>Logs, Alerts, Models, Datasets"]
        auth["Auth Service<br/>JWT + phân quyền role"]
        dbsvc["Database Service<br/>truy vấn và ghi dữ liệu"]
        infer["OCSVM Inference Service<br/>chuẩn hóa feature + chấm điểm"]
        demo["Demo Analysis Pipeline<br/>event -> feature -> anomaly"]
        llm["Alert Explanation Service<br/>OpenRouter hoặc fallback"]
        agent["Agent wrapper<br/>luồng giải thích cảnh báo"]

        routes --> auth
        routes --> dbsvc
        routes --> infer
        routes --> demo
        demo --> llm
        agent --> llm
    end

    subgraph storage["Lưu trữ"]
        postgres[("PostgreSQL<br/>accounts, users, devices,<br/>raw logs, events, alerts,<br/>features, model metadata")]
        model[("OCSVM artifact<br/>weights/*.joblib")]
        artifacts[("ML artifacts & reports<br/>artifacts/ + eval/results/")]
    end

    subgraph offline["Pipeline ML offline"]
        preprocess["Preprocessing<br/>CSV -> user-day features"]
        training["Training / Evaluation"]
        preprocess --> training
    end

    analyst --> pages
    client <-->|"JSON/HTTP + Bearer JWT"| routes
    sources -->|"import / ingest"| routes
    dbsvc <-->|"SQL"| postgres
    infer -->|"load model"| model
    demo -->|"load model"| model
    llm <-->|"alert context / Vietnamese explanation"| openrouter

    sources -.-> preprocess
    preprocess -.-> artifacts
    training -.-> artifacts
    training -.-> model
```

Quy ước: mũi tên liền là luồng runtime; mũi tên nét đứt là xử lý ML offline.

## 2. Luồng dữ liệu runtime

```mermaid
sequenceDiagram
    autonumber
    actor User as SOC Analyst / Admin
    participant UI as React Frontend
    participant API as FastAPI
    participant DB as PostgreSQL
    participant CSV as CERT r4.2 CSV
    participant ML as OCSVM Model
    participant LLM as OpenRouter

    rect rgb(238, 245, 255)
        Note over User,DB: Xác thực và tra cứu
        User->>UI: Đăng nhập
        UI->>API: POST /api/auth/login
        API->>DB: Kiểm tra tài khoản
        DB-->>API: Account + password hash + role
        API-->>UI: JWT + thông tin người dùng
        UI->>UI: Lưu session vào localStorage
        UI->>API: GET dashboard/users/devices/logs/alerts + Bearer JWT
        API->>DB: Truy vấn dữ liệu
        DB-->>API: Bản ghi nghiệp vụ
        API-->>UI: JSON hiển thị
    end

    rect rgb(244, 250, 240)
        Note over User,DB: Nhập dữ liệu
        User->>UI: Chạy CERT data import
        UI->>API: POST /api/datasets/cert-r42/import
        API->>CSV: Đọc dữ liệu cấu hình bởi DATA_DIR
        CSV-->>API: Logon, device, file, HTTP và email
        API->>DB: Upsert users, devices, event logs và model metadata
        DB-->>API: Thống kê import
        API-->>UI: Trạng thái + summary
    end

    rect rgb(255, 247, 235)
        Note over User,LLM: Phân tích bất thường và tạo cảnh báo
        User->>UI: Chạy demo analysis
        UI->>API: POST /api/demo/analyze
        alt Request có events
            API->>API: Dùng events trong payload
        else Không có events
            API->>CSV: Tìm events theo user
            alt Không tìm thấy trong CSV
                API->>DB: Tìm event_logs theo user
                DB-->>API: Events
            end
        end
        API->>API: Trích xuất feature hành vi
        API->>ML: predict + decision_function
        ML-->>API: anomaly score + nhãn
        opt Phát hiện bất thường
            API->>LLM: Gửi alert context
            alt Có API key và provider phản hồi
                LLM-->>API: Giải thích tiếng Việt
            else Không có API key
                API->>API: Tạo giải thích fallback
            else Provider trả lỗi
                LLM-->>API: Thông báo lỗi LLM
            end
            API->>DB: Tạo alert
        end
        API-->>UI: Kết quả phân tích
    end
```

## 3. Trách nhiệm và dữ liệu chính

| Thành phần | Trách nhiệm | Dữ liệu vào | Dữ liệu ra |
|---|---|---|---|
| React Frontend | Xác thực, điều hướng và hiển thị nghiệp vụ cho analyst/admin | Tương tác người dùng, JSON từ API | API request, dashboard và cảnh báo |
| FastAPI Routes | Điểm vào HTTP, kiểm tra schema, JWT và role | JSON, query params, Bearer token | JSON response, lệnh gọi service |
| Auth Service | Hash/verify mật khẩu, tạo và giải mã JWT | Credentials, account, JWT | Identity và role đã xác thực |
| Database Service | Quản lý accounts, users, devices, logs, alerts và metadata model | Payload đã kiểm tra | Bản ghi PostgreSQL |
| Demo Analysis Pipeline | Chuyển event thành feature và điều phối phân tích demo | Events từ request, CSV hoặc DB | Risk score, anomaly score, top factors |
| OCSVM Inference Service | Nạp model đã huấn luyện và suy luận feature vector | Feature dictionary / DataFrame | Nhãn anomaly, score, severity |
| LLM Explanation Service | Sinh giải thích cảnh báo tiếng Việt; có fallback cục bộ | Alert context | Nội dung giải thích |
| Offline ML Pipeline | Tiền xử lý CERT, tạo feature, huấn luyện và đánh giá | CSV CERT r4.2, LDAP, psychometric | Feature matrix, model artifact, báo cáo |

## 4. Ranh giới triển khai

- Backend khởi tạo schema PostgreSQL khi FastAPI startup.
- Frontend gọi API qua `VITE_API_BASE_URL`; các request bảo vệ gửi `Authorization: Bearer <jwt>`.
- Runtime không huấn luyện model. Hai endpoint model và demo analysis nạp OCSVM artifact đã có.
- Pipeline trong `src/services/ueba_ml/pipelines/` chạy offline và ghi kết quả vào `artifacts/` cùng `eval/results/`.
- `src/agents/` hiện là wrapper mỏng cho luồng giải thích; đường gọi demo hiện tại gọi explanation service trực tiếp.
- OpenRouter là phụ thuộc tùy chọn. Khi thiếu API key, hệ thống dùng giải thích dựa trên rule; lỗi từ provider được trả thành thông báo trong phần giải thích.
