# 0 - Idea

## Vấn đề cần giải quyết
Doanh nghiệp khó phát hiện sớm **insider threat** và **account compromise** vì tín hiệu bất thường nằm rải rác trong nhiều nguồn log (đăng nhập, file, email, web, thiết bị). Các hệ thống cũ thường trả về cảnh báo thô, thiếu ngữ cảnh để analyst xử lý nhanh.

## Ý tưởng sản phẩm
Xây dựng **UEBA Endpoint Monitoring** theo hướng web/app hoàn chỉnh:
- Thu thập và chuẩn hóa log endpoint (giai đoạn MVP dùng CERT r4.2 làm nguồn chính).
- Học baseline hành vi theo user/device và phát hiện anomaly bằng ML.
- Quy đổi anomaly thành risk score 0-100, tạo alert có mức độ ưu tiên.
- Cung cấp explanation bằng LLM (hoặc rule-based fallback) để analyst hiểu nguyên nhân.

## Người dùng mục tiêu
- **Security Admin**: theo dõi toàn cục, quản lý user/device, điều phối xử lý alert.
- **Security Analyst**: triage alert, đọc explanation và timeline để điều tra.
- **Data/ML Engineer**: vận hành pipeline import, feature engineering, training, inference.

## Vòng lặp giá trị cốt lõi (Core Value Loops)

### 1) Model loop (offline)
`Import CERT r4.2 -> Normalize events -> Feature engineering -> Train model -> Validate metrics -> Version model`

### 2) Ops loop (online)
`Ingest/infer -> Risk scoring -> Tạo alert -> Explanation -> Analyst xử lý -> Feedback -> Retrain định kỳ`

## Giá trị khác biệt của MVP
- Không chỉ hiển thị log: hệ thống tạo **risk context + explanation**.
- Bám sát bài toán thực tế endpoint công ty cấp (không dùng dữ liệu mock làm nguồn chính).
- Có khả năng mở rộng từ batch dataset sang endpoint agent thật qua API ingest.