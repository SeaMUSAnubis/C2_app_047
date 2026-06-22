# Báo cáo huấn luyện Isolation Forest

## Mục tiêu

Huấn luyện mô hình Isolation Forest để phát hiện anomaly trên bảng hành vi
`user + date` đã được tạo từ bước tiền xử lý UEBA. Đây là bài toán unsupervised,
vì vậy report tập trung vào cấu hình train, phân phối điểm anomaly, số lượng
record bị gắn cờ và các feature nổi bật ở nhóm anomaly.

## Dữ liệu train

- Input: `artifacts/preprocessing/iforest_feature_matrix.csv`
- Số dòng: 47
- Số numeric feature: 65
- Số user: 47
- Khoảng ngày: `2010-01-02` đến `2010-01-02`
- NaN sau khi chuẩn bị matrix: 0
- Infinite values sau khi chuẩn bị matrix: 0

## Cấu hình mô hình

- Pipeline: `SimpleImputer(strategy=median) -> StandardScaler -> IsolationForest`
- `n_estimators`: 300
- `max_samples`: 10000
- `contamination`: 0.02
- `random_state`: 42
- `n_jobs`: -1
- Thời gian train + scoring: 0.30 giây
- `sklearn`: 1.9.0

## Kết quả scoring

- Số anomaly user-day: 1
- Tỷ lệ anomaly: 2.13%
- Ngưỡng anomaly score: 0.658636
- `anomaly_score = -score_samples`; điểm càng cao càng bất thường.
- `decision_score < 0` được gắn nhãn anomaly.

Score distribution:

| Metric | anomaly_score | decision_score |
|---|---:|---:|
| min | 0.334850 | -0.017324 |
| p05 | 0.337798 | 0.009734 |
| p50 | 0.411113 | 0.230199 |
| p95 | 0.631578 | 0.303514 |
| max | 0.658636 | 0.306462 |

## Top users có nhiều anomaly

- `MOH0273`: 1
- `AHC0142`: 0
- `ABC0174`: 0
- `ALB0892`: 0
- `AMW0392`: 0
- `AOK0844`: 0
- `AJR0319`: 0
- `BDI0533`: 0
- `BQS0525`: 0
- `BRB0355`: 0

## Top ngày có nhiều anomaly

- `2010-01-02`: 1

## Một số anomaly nổi bật

- `MOH0273` `2010-01-02` score=0.658636, decision=-0.017324, drivers: device_disconnect_count=4 (z=4.00); device_event_count=8 (z=3.84); device_after_hours_count=8 (z=3.84); device_weekend_count=8 (z=3.84); device_connect_count=4 (z=3.66)
- `RRC0553` `2010-01-02` score=0.639806, decision=0.001506, drivers: file_event_count=23 (z=5.34); file_weekend_count=23 (z=5.34); file_after_hours_count=23 (z=5.34); file_doc_count=13 (z=5.14); file_pdf_count=4 (z=4.92)
- `LRR0148` `2010-01-02` score=0.635303, decision=0.006009, drivers: email_attachment_sum=8 (z=3.62); email_after_hours_count=13 (z=3.58); email_weekend_count=13 (z=3.58); email_event_count=13 (z=3.58); http_event_count=10 (z=2.76)
- `HSB0196` `2010-01-02` score=0.622887, decision=0.018426, drivers: email_attachment_rate=1.5 (z=5.39); file_per_device_connect=6.5 (z=4.03); file_avg_hour=8.769 (z=3.33); file_avg_content_words=46.31 (z=3.12); file_doc_count=8 (z=3.06)
- `NWK0215` `2010-01-02` score=0.587922, decision=0.053391, drivers: email_external_recipient_sum=21 (z=5.84); email_attachment_sum=10 (z=4.61); email_recipient_sum=41 (z=4.32); email_after_hours_count=13 (z=3.58); email_weekend_count=13 (z=3.58)
- `AJR0319` `2010-01-02` score=0.579523, decision=0.061789, drivers: email_recipient_sum=39 (z=4.09); email_weekend_count=14 (z=3.88); email_after_hours_count=14 (z=3.88); email_event_count=14 (z=3.88); email_attachment_sum=6 (z=2.64)
- `LAP0338` `2010-01-02` score=0.561696, decision=0.079616, drivers: http_after_hours_count=12 (z=3.40); http_weekend_count=12 (z=3.40); http_event_count=12 (z=3.40); http_avg_hour=7 (z=2.06); http_avg_path_depth=3 (z=2.05)
- `IRM0931` `2010-01-02` score=0.548554, decision=0.092758, drivers: http_after_hours_count=12 (z=3.40); http_weekend_count=12 (z=3.40); http_event_count=12 (z=3.40); logon_pc_variety_score=4 (z=2.46); logon_after_hours_count=4 (z=2.46)
- `HPH0075` `2010-01-02` score=0.547548, decision=0.093764, drivers: file_avg_hour=9.3 (z=3.55); file_avg_content_words=47.4 (z=3.20); device_connect_count=3 (z=2.64); file_doc_count=7 (z=2.64); file_pdf_count=2 (z=2.32)
- `HVB0037` `2010-01-02` score=0.506683, decision=0.134630, drivers: email_avg_size=3.197e+04 (z=2.40); email_external_recipient_sum=9 (z=2.33); email_avg_hour=7.8 (z=2.11); logon_logoff_count=1 (z=1.92); email_external_recipient_rate=1.8 (z=1.77)
- `IIW0249` `2010-01-02` score=0.485960, decision=0.155352, drivers: device_disconnect_count=3 (z=2.90); device_event_count=6 (z=2.78); device_after_hours_count=6 (z=2.78); device_weekend_count=6 (z=2.78); device_connect_count=3 (z=2.64)
- `JDC0030` `2010-01-02` score=0.481685, decision=0.159628, drivers: email_external_recipient_rate=5 (z=5.48); email_recipient_rate=5 (z=4.12); email_avg_size=3.257e+04 (z=2.46); email_avg_hour=8 (z=2.18); team_frequency=0.1489 (z=1.89)
- `NGF0157` `2010-01-02` score=0.469857, decision=0.171455, drivers: http_after_hours_count=8 (z=2.13); http_weekend_count=8 (z=2.13); http_event_count=8 (z=2.13); http_avg_hour=7 (z=2.06); http_avg_path_depth=3 (z=2.05)
- `ABC0174` `2010-01-02` score=0.464622, decision=0.176690, drivers: http_avg_hour=7 (z=2.06); http_avg_path_depth=3 (z=2.05); logon_logoff_count=1 (z=1.92); logon_avg_hour=11.67 (z=1.80); logon_weekend_count=3 (z=1.31)
- `NOB0181` `2010-01-02` score=0.459253, decision=0.182059, drivers: logon_after_hours_count=4 (z=2.46); logon_pc_variety_score=4 (z=2.46); logon_event_count=4 (z=2.46); logon_weekend_count=4 (z=2.46); logon_logon_count=3 (z=2.15)

## Feature khác biệt nhất giữa anomaly và normal

Các giá trị dưới đây là so sánh trung bình anomaly vs normal, chuẩn hóa theo độ
lệch chuẩn toàn bộ dữ liệu. Đây không phải feature importance nội tại chính xác
của Isolation Forest, nhưng hữu ích để đọc nhanh kiểu hành vi đang bị model gắn
cờ.

- `device_disconnect_count`: anomaly_mean=4, normal_mean=0.2826, lift=4.045
- `device_weekend_count`: anomaly_mean=8, normal_mean=0.6087, lift=3.886
- `device_event_count`: anomaly_mean=8, normal_mean=0.6087, lift=3.886
- `device_after_hours_count`: anomaly_mean=8, normal_mean=0.6087, lift=3.886
- `device_connect_count`: anomaly_mean=4, normal_mean=0.3261, lift=3.701
- `file_pdf_count`: anomaly_mean=3, normal_mean=0.1522, lift=3.659
- `file_avg_content_words`: anomaly_mean=48.57, normal_mean=3.152, lift=3.325
- `file_avg_hour`: anomaly_mean=8.143, normal_mean=0.5743, lift=3.101
- `email_external_recipient_rate`: anomaly_mean=2.5, normal_mean=0.2252, lift=2.610
- `after_hours_events`: anomaly_mean=24, normal_mean=5.826, lift=2.338
- `total_events`: anomaly_mean=24, normal_mean=5.826, lift=2.338
- `weekend_events`: anomaly_mean=24, normal_mean=5.826, lift=2.338
- `http_avg_hour`: anomaly_mean=7, normal_mean=1.215, lift=2.081
- `http_avg_path_depth`: anomaly_mean=3, normal_mean=0.5217, lift=2.077
- `device_avg_hour`: anomaly_mean=8.25, normal_mean=1.35, lift=2.063
- `email_avg_hour`: anomaly_mean=7, normal_mean=1.337, lift=1.867
- `email_recipient_rate`: anomaly_mean=2.5, normal_mean=0.4441, lift=1.859
- `email_avg_size`: anomaly_mean=2.363e+04, normal_mean=4910, lift=1.669
- `http_weekend_count`: anomaly_mean=6, normal_mean=1.217, lift=1.506
- `http_after_hours_count`: anomaly_mean=6, normal_mean=1.217, lift=1.506

## File đã sinh

- Model artifact: `artifacts/models/iforest_model.joblib`
- Metadata: `artifacts/models/iforest_metadata.json`
- Toàn bộ score: `artifacts/models/iforest_anomaly_scores.csv`
- Top anomaly: `artifacts/models/iforest_top_anomalies.csv`
- Feature lift: `artifacts/evaluation/iforest_feature_lift.csv`

## Biểu đồ

- `eval/results/figures/iforest/iforest_score_distribution.png`
- `eval/results/figures/iforest/iforest_anomalies_by_date.png`
- `eval/results/figures/iforest/iforest_top_anomaly_users.png`

## Lưu ý vận hành

Vì dữ liệu không có nhãn ground truth trong pipeline hiện tại, chưa thể báo cáo
precision/recall/F1. Nên dùng report này để chọn `contamination` và kiểm tra
top anomaly thủ công trước khi tích hợp scoring vào `src/api` và dashboard.
