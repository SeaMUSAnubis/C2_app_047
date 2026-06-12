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
- `n_estimators`: 10
- `max_samples`: auto
- `contamination`: 0.02
- `random_state`: 42
- `n_jobs`: -1
- Thời gian train + scoring: 0.04 giây
- `sklearn`: 1.7.2

## Kết quả scoring

- Số anomaly user-day: 1
- Tỷ lệ anomaly: 2.13%
- Ngưỡng anomaly score: 0.753404
- `anomaly_score = -score_samples`; điểm càng cao càng bất thường.
- `decision_score < 0` được gắn nhãn anomaly.

Score distribution:

| Metric | anomaly_score | decision_score |
|---|---:|---:|
| min | 0.346801 | -0.071127 |
| p05 | 0.347514 | 0.060116 |
| p50 | 0.411375 | 0.270902 |
| p95 | 0.622161 | 0.334763 |
| max | 0.753404 | 0.335475 |

## Top users có nhiều anomaly

- `RRC0553`: 1
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

- `RRC0553` `2010-01-02` score=0.753404, decision=-0.071127, drivers: file_event_count=23 (z=5.34); file_weekend_count=23 (z=5.34); file_after_hours_count=23 (z=5.34); file_doc_count=13 (z=5.14); file_pdf_count=4 (z=4.92)
- `MOH0273` `2010-01-02` score=0.676092, decision=0.006185, drivers: device_disconnect_count=4 (z=4.00); device_event_count=8 (z=3.84); device_after_hours_count=8 (z=3.84); device_weekend_count=8 (z=3.84); device_connect_count=4 (z=3.66)
- `LRR0148` `2010-01-02` score=0.637391, decision=0.044886, drivers: email_attachment_sum=8 (z=3.62); email_after_hours_count=13 (z=3.58); email_weekend_count=13 (z=3.58); email_event_count=13 (z=3.58); http_event_count=10 (z=2.76)
- `NWK0215` `2010-01-02` score=0.586625, decision=0.095652, drivers: email_external_recipient_sum=21 (z=5.84); email_attachment_sum=10 (z=4.61); email_recipient_sum=41 (z=4.32); email_after_hours_count=13 (z=3.58); email_weekend_count=13 (z=3.58)
- `AJR0319` `2010-01-02` score=0.554954, decision=0.127323, drivers: email_recipient_sum=39 (z=4.09); email_weekend_count=14 (z=3.88); email_after_hours_count=14 (z=3.88); email_event_count=14 (z=3.88); email_attachment_sum=6 (z=2.64)
- `IRM0931` `2010-01-02` score=0.546735, decision=0.135542, drivers: http_after_hours_count=12 (z=3.40); http_weekend_count=12 (z=3.40); http_event_count=12 (z=3.40); logon_pc_variety_score=4 (z=2.46); logon_after_hours_count=4 (z=2.46)
- `HPH0075` `2010-01-02` score=0.542441, decision=0.139836, drivers: file_avg_hour=9.3 (z=3.55); file_avg_content_words=47.4 (z=3.20); device_connect_count=3 (z=2.64); file_doc_count=7 (z=2.64); file_pdf_count=2 (z=2.32)
- `HSB0196` `2010-01-02` score=0.530122, decision=0.152155, drivers: email_attachment_rate=1.5 (z=5.39); file_per_device_connect=6.5 (z=4.03); file_avg_hour=8.769 (z=3.33); file_avg_content_words=46.31 (z=3.12); file_doc_count=8 (z=3.06)
- `LAP0338` `2010-01-02` score=0.493902, decision=0.188375, drivers: http_after_hours_count=12 (z=3.40); http_weekend_count=12 (z=3.40); http_event_count=12 (z=3.40); http_avg_hour=7 (z=2.06); http_avg_path_depth=3 (z=2.05)
- `IKP0472` `2010-01-02` score=0.490746, decision=0.191531, drivers: logon_after_hours_count=4 (z=2.46); logon_pc_variety_score=4 (z=2.46); logon_event_count=4 (z=2.46); logon_weekend_count=4 (z=2.46); logon_logon_count=3 (z=2.15)
- `HVB0037` `2010-01-02` score=0.480422, decision=0.201855, drivers: email_avg_size=3.197e+04 (z=2.40); email_external_recipient_sum=9 (z=2.33); email_avg_hour=7.8 (z=2.11); logon_logoff_count=1 (z=1.92); email_external_recipient_rate=1.8 (z=1.77)
- `HLH0512` `2010-01-02` score=0.462856, decision=0.219421, drivers: O=15 (z=-5.66); A=22 (z=-2.52); N=32 (z=1.66); department_frequency=0.2766 (z=1.51); role_frequency=0.2553 (z=1.48)
- `NOB0181` `2010-01-02` score=0.459806, decision=0.222470, drivers: logon_after_hours_count=4 (z=2.46); logon_pc_variety_score=4 (z=2.46); logon_event_count=4 (z=2.46); logon_weekend_count=4 (z=2.46); logon_logon_count=3 (z=2.15)
- `WPR0368` `2010-01-02` score=0.455487, decision=0.226790, drivers: logon_avg_hour=12 (z=2.03); logon_logoff_count=1 (z=1.92); functional_unit_frequency=0.08511 (z=-1.38); logon_weekend_count=3 (z=1.31); logon_pc_variety_score=3 (z=1.31)
- `JDC0030` `2010-01-02` score=0.428235, decision=0.254042, drivers: email_external_recipient_rate=5 (z=5.48); email_recipient_rate=5 (z=4.12); email_avg_size=3.257e+04 (z=2.46); email_avg_hour=8 (z=2.18); team_frequency=0.1489 (z=1.89)

## Feature khác biệt nhất giữa anomaly và normal

Các giá trị dưới đây là so sánh trung bình anomaly vs normal, chuẩn hóa theo độ
lệch chuẩn toàn bộ dữ liệu. Đây không phải feature importance nội tại chính xác
của Isolation Forest, nhưng hữu ích để đọc nhanh kiểu hành vi đang bị model gắn
cờ.

- `file_event_count`: anomaly_mean=23, normal_mean=0.6522, lift=5.402
- `file_after_hours_count`: anomaly_mean=23, normal_mean=0.6522, lift=5.402
- `file_weekend_count`: anomaly_mean=23, normal_mean=0.6522, lift=5.402
- `file_doc_count`: anomaly_mean=13, normal_mean=0.3913, lift=5.199
- `file_pdf_count`: anomaly_mean=4, normal_mean=0.1304, lift=4.971
- `file_per_device_connect`: anomaly_mean=7.667, normal_mean=0.2518, lift=4.855
- `file_avg_content_words`: anomaly_mean=51.3, normal_mean=3.093, lift=3.529
- `weekend_events`: anomaly_mean=31, normal_mean=5.674, lift=3.258
- `after_hours_events`: anomaly_mean=31, normal_mean=5.674, lift=3.258
- `total_events`: anomaly_mean=31, normal_mean=5.674, lift=3.258
- `file_avg_hour`: anomaly_mean=8.348, normal_mean=0.5698, lift=3.187
- `device_disconnect_count`: anomaly_mean=3, normal_mean=0.3043, lift=2.933
- `device_after_hours_count`: anomaly_mean=6, normal_mean=0.6522, lift=2.812
- `device_weekend_count`: anomaly_mean=6, normal_mean=0.6522, lift=2.812
- `device_event_count`: anomaly_mean=6, normal_mean=0.6522, lift=2.812
- `device_connect_count`: anomaly_mean=3, normal_mean=0.3478, lift=2.672
- `device_avg_hour`: anomaly_mean=8.667, normal_mean=1.341, lift=2.190
- `role_frequency`: anomaly_mean=0.02128, normal_mean=0.1221, lift=-1.094
- `team_frequency`: anomaly_mean=0.02128, normal_mean=0.06568, lift=-0.986
- `department_frequency`: anomaly_mean=0.08511, normal_mean=0.1494, lift=-0.746

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
