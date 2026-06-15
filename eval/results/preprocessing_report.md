# Báo cáo tiền xử lý dữ liệu UEBA

## Ngữ cảnh đề tài

Các tài liệu đã đọc gồm `docs/planning/PRD.md`, `docs/planning/BRIEF.md`,
`docs/planning/UEBA_REQUIREMENTS.md`, `data/raw/cert-r4.2/readme.txt` và schema mẫu trong
`data/sample/cert-r4.2-small/`. Đề tài là UEBA Endpoint Monitoring cho bài toán insider
threat/account compromise trên CERT r4.2. Các nguồn tín hiệu bắt buộc gồm
`logon`, `device`, `file`, `http`, `email`, LDAP snapshots và psychometric
attributes nếu có.

Mục tiêu tiền xử lý là gom log rời rạc thành bảng hành vi theo ngày của từng
user (`user + date`), sau đó xuất ma trận số có thể đưa trực tiếp vào mô hình
Isolation Forest.

## Cấu hình chạy

- Thư mục dữ liệu vào: `data/sample/cert-r4.2-small`
- Thư mục output: `artifacts/preprocessing`
- Chunk size: `250,000` dòng
- Giả định giờ làm việc: `7:00 <= hour < 18:00`,
  từ thứ Hai đến thứ Sáu
- Mức aggregate: `user + date`

## Tổng quan xử lý nguồn dữ liệu

| Nguồn | Tồn tại | Dòng đã đọc | Số chunk | Dung lượng MB | Dòng lỗi ngày | Timestamp nhỏ nhất | Timestamp lớn nhất |
|---|---:|---:|---:|---:|---:|---|---|
| logon | yes | 87 | 1 | 0.01 | 0 | 2010-01-02 06:49:00 | 2010-01-02 15:56:00 |
| device | yes | 36 | 1 | 0.0 | 0 | 2010-01-02 07:21:06 | 2010-01-02 10:27:26 |
| file | yes | 53 | 1 | 0.02 | 0 | 2010-01-02 07:23:14 | 2010-01-02 10:26:50 |
| email | yes | 54 | 1 | 0.03 | 0 | 2010-01-02 07:11:45 | 2010-01-02 08:39:01 |
| http | yes | 62 | 1 | 0.03 | 0 | 2010-01-02 06:55:16 | 2010-01-02 07:43:47 |

LDAP snapshots: 18 file, 16,743 dòng.

Psychometric: 148 dòng.

## Kết quả output

- Số dòng user-day: 47
- Số user duy nhất: 47
- Khoảng ngày: `2010-01-02` đến `2010-01-02`
- Tổng event đã biểu diễn trong aggregate: 292
- Số feature số cho iForest: 65
- Feature đầy đủ, dễ đọc: `artifacts/preprocessing/user_day_features.csv`
- Ma trận số cho iForest: `artifacts/preprocessing/iforest_feature_matrix.csv`
- Danh sách cột feature: `artifacts/preprocessing/iforest_feature_columns.json`

## Nhóm feature đã tạo

- Volume: số lượng event hằng ngày cho logon, device, file, email và HTTP.
- Thời gian: số event ngoài giờ, cuối tuần, giờ trung bình, thứ trong tuần,
  tháng và cờ ngày cuối tuần.
- Hành vi có rủi ro exfiltration: số lần cắm USB/device, số file copy, số file
  document/PDF, tỷ lệ file/device connect, tỷ lệ attachment, tỷ lệ người nhận
  email ngoài công ty và độ sâu path HTTP trung bình.
- Baseline theo user: z-score theo từng user cho các tín hiệu volume/risk chính.
- Enrichment: mã hóa tần suất role/department từ LDAP và điểm Big Five nếu có.

## Các cột feature số

- `logon_event_count`
- `logon_logon_count`
- `logon_logoff_count`
- `logon_after_hours_count`
- `logon_weekend_count`
- `logon_pc_variety_score`
- `device_event_count`
- `device_connect_count`
- `device_disconnect_count`
- `device_after_hours_count`
- `device_weekend_count`
- `file_event_count`
- `file_after_hours_count`
- `file_weekend_count`
- `file_doc_count`
- `file_pdf_count`
- `email_event_count`
- `email_after_hours_count`
- `email_weekend_count`
- `email_attachment_sum`
- `email_recipient_sum`
- `email_external_recipient_sum`
- `http_event_count`
- `http_after_hours_count`
- `http_weekend_count`
- `total_events`
- `after_hours_events`
- `weekend_events`
- `after_hours_ratio`
- `weekend_ratio`
- `logon_avg_hour`
- `device_avg_hour`
- `file_avg_hour`
- `email_avg_hour`
- `http_avg_hour`
- `file_avg_content_words`
- `email_avg_size`
- `email_attachment_rate`
- `email_recipient_rate`
- `email_external_recipient_rate`
- `http_avg_path_depth`
- `file_per_device_connect`
- `day_of_week`
- `month`
- `is_weekend_day`
- `total_events_user_zscore`
- `after_hours_events_user_zscore`
- `weekend_events_user_zscore`
- `logon_event_count_user_zscore`
- `device_event_count_user_zscore`
- `file_event_count_user_zscore`
- `email_event_count_user_zscore`
- `http_event_count_user_zscore`
- `email_attachment_sum_user_zscore`
- `email_external_recipient_sum_user_zscore`
- `file_per_device_connect_user_zscore`
- `O`
- `C`
- `E`
- `A`
- `N`
- `role_frequency`
- `department_frequency`
- `functional_unit_frequency`
- `team_frequency`

## Biểu đồ đã tạo

- `artifacts/preprocessing/figures/event_volume_by_source.png`
- `artifacts/preprocessing/figures/daily_event_volume.png`
- `artifacts/preprocessing/figures/top_users_by_event_volume.png`
- `artifacts/preprocessing/figures/after_hours_ratio_distribution.png`
- `artifacts/preprocessing/figures/feature_correlation_heatmap.png`

## Ghi chú cho Isolation Forest

Dùng `iforest_feature_matrix.csv` làm dữ liệu đầu vào cho model. Giữ `user` và
`date` làm cột định danh, còn các cột còn lại là numeric feature để train
Isolation Forest. Pipeline hiện tại chưa train model; nó chuẩn bị dữ liệu và
biểu đồ chẩn đoán trước bước huấn luyện.

Với dữ liệu gốc, các CSV lớn không được load toàn bộ vào RAM. Mỗi nguồn được đọc
bằng `pandas.read_csv(..., chunksize=250,000)`, aggregate ngay về
`user-date`, rồi mới merge thành bảng feature cuối.
