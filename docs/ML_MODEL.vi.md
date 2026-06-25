# Tài Liệu Mô Hình ML

Tài liệu này mô tả mô hình OCSVM (One-Class Support Vector Machine) được dùng
cho anomaly detection trong hệ thống UEBA Endpoint Monitoring.

> **Trạng thái (v0.1.0)**: Mô hình là OCSVM đã train sẵn trên CERT r4.2
> (`ocsvm_cert_r42_chunked.joblib`). **Không retrain trong production**;
> việc retrain là quy trình offline thủ công (xem §5).

---

## 1. Tại sao OCSVM?

UEBA là bài toán **one-class classification**: ta có nhiều hành vi
"bình thường" (nhân viên làm việc) và một lượng nhỏ hành vi "bất
thường" (insider threat, account compromise, data exfiltration).
Class imbalance cực kỳ nghiêm trọng (~99.99% bình thường).

OCSVM (Schölkopf et al., 2001) phù hợp với bài toán này:
- Chỉ train trên **dữ liệu bình thường** (không cần labeled anomalies).
- Học một decision boundary bao quanh vùng "bình thường".
- Bất cứ thứ gì nằm ngoài boundary sẽ bị flag là bất thường.
- Nhanh khi inference (single SVM decision trên 20 features).

Các lựa chọn thay thế đã xem xét:
| Model | Ưu | Nhược | Quyết định |
|---|---|---|---|
| **OCSVM** | One-class, nhanh, đơn giản | Nhạy với `nu` (rejection rate) | ✅ Mặc định |
| Isolation Forest | Scale tốt, không cần tune `nu` | Ít interpretable | (dự kiến) |
| Autoencoder | Bắt được pattern non-linear phức tạp | Train chậm, khó debug | (tương lai) |
| LLM-based | "Hiểu" context | Đắt, chậm, không deterministic | Loại (chỉ dùng cho explanation) |

---

## 2. Features

OCSVM hoạt động trên **vector 20 chiều** cho mỗi user trong mỗi window
(mặc định: 24h rolling). Features được tính bởi
`demo_pipeline.extract_features` (phía server) từ bảng events.

| # | Feature | Ý nghĩa |
|---|---|---|
| 1 | `n_logon` | Số lượng logon events |
| 2 | `n_logon_afterhours` | Logon ngoài giờ làm việc |
| 3 | `n_logon_weekend` | Logon vào cuối tuần |
| 4 | `n_logon_other_pc` | Logon từ PC user không hay dùng |
| 5 | `n_distinct_pc` | Số PC khác nhau user login vào |
| 6 | `first_logon_hour` | Giờ của logon đầu tiên trong window (0-23) |
| 7 | `last_logon_hour` | Giờ của logon cuối cùng (0-23) |
| 8 | `n_device_connect` | Số USB connect events |
| 9 | `n_device_afterhours` | USB connect ngoài giờ |
| 10 | `n_device_weekend` | USB connect vào cuối tuần |
| 11 | `n_file_copy` | Số file copy events |
| 12 | `n_file_exe` | File copy với extension `.exe` |
| 13 | `n_file_doc` | File copy với extension `.doc/.docx` |
| 14 | `n_file_zip` | File copy với extension `.zip` |
| 15 | `n_file_afterhours` | File copy ngoài giờ |
| 16 | `n_email` | Số email events |
| 17 | `n_email_external` | Email có external recipients |
| 18 | `email_size_total` | Tổng bytes gửi trong window |
| 19 | `n_http_wikileaks` | HTTP visits đến wikileaks.org |
| 20 | `n_http_jobsearch` | HTTP visits đến job-search sites |

(Cộng thêm OCEAN personality features `O`, `C`, `E`, `A`, `N` khi có —
mặc định 3.0 trong production vì hầu hết nhân viên không có psychometric
data.)

### 2.1 — Feature engineering

Features được tính trong `src/backend/app/services/demo_pipeline.py`
(hàm `extract_features`). Đây là phiên bản đơn giản hóa của CERT r4.2
preprocessing pipeline (xem
`src/ml/services/ueba_ml/pipelines/preprocess.py` cho phiên bản đầy đủ).

Cho production thật, features nên được tính trên **rolling window**
(ví dụ 24h gần nhất), không phải toàn bộ event history. Hiện tại
`user_scoring.score_user` làm điều này — fetch events với
`timestamp >= now - 24h`.

### 2.2 — Event flattening

Events trong `event_logs` có `metadata_json` và `raw_json` dưới dạng cột
JSON. Scoring service flatten chúng thành top-level fields trước khi
extract features (ví dụ `filename` từ `raw_payload`). Điều này quan trọng
— OCSVM không biết về JSON.

---

## 3. Model training

### 3.1 — Dữ liệu training

Mô hình được train trên **CERT r4.2 insider threat dataset** (CERT,
Carnegie Mellon). Tập training chứa ~70M events từ ~1000 nhân viên trong
~500 ngày. Chỉ các event "bình thường" (không có nhãn insider threat) được
dùng để train.

### 3.2 — Hyperparameters

| Param | Giá trị | Ý nghĩa |
|---|---|---|
| `kernel` | `rbf` | Radial Basis Function (Gaussian) |
| `nu` | `0.005` | Cận trên của tỷ lệ training error (cho phép 0.5% train set "bất thường") |
| `gamma` | `scale` | `1 / (n_features * X.var())` |

Các giá trị này được bake vào file `.joblib`. Để inspect:
```python
import joblib
m = joblib.load("src/ml/weights/ocsvm_cert_r42_chunked.joblib")
print(m["pipeline"].get_params())
print("feature_columns:", m["feature_columns"])
```

### 3.3 — Reproduce training

```bash
# 1. Preprocess raw CERT r4.2 CSVs:
bash src/ml/scripts/run_preprocessing.sh

# 2. Train:
bash src/ml/scripts/train_model.sh

# Output: src/ml/weights/ocsvm_cert_r42_chunked.joblib
```

(Xem `src/ml/scripts/` cho pipeline đầy đủ. Cần `pandas` + `scikit-learn`.)

---

## 4. Inference

### 4.1 — Flow

```
1. Normalizer insert event_logs (Phase 3).
2. user_scoring.score_user(user_id):
     a. Fetch events cho user trong N phút gần nhất (configurable, default 24h).
     b. Flatten metadata/raw JSON thành top-level fields.
     c. demo_pipeline.extract_features(events) → 1-row DataFrame.
     d. run_ocsvm_inference(features_dict) → ModelInferResponse.
     e. INSERT ml_anomaly_scores row.
     f. Nếu is_anomaly AND risk_score >= ML_SCORING_ALERT_MIN_RISK:
        - create_alert(...)
        - UPDATE ml_anomaly_scores.created_alert_id
```

### 4.2 — Risk score → severity

| `risk_score` range | `severity` |
|---|---|
| 0–30 | `low` |
| 31–60 | `medium` |
| 61–80 | `high` |
| 81–100 | `critical` |

Mapping trong `src/ml/services/ueba_ml/inference.py:_severity`.

### 4.3 — Anomaly explanation

Khi alert được tạo, hệ thống cũng sinh giải thích 3 dòng tiếng Việt
qua LLM (Mistral). Xem `src/backend/app/services/llm.py`.

---

## 5. Re-training

Mô hình CERT r4.2 đã train sẵn là **khởi điểm hợp lý** nhưng không hoàn
hảo cho mọi tổ chức. Để có kết quả tốt nhất, retrain trên dữ liệu của
bạn.

### 5.1 — Khi nào retrain

- **Mỗi 6 tháng** (bắt pattern theo mùa).
- **Sau thay đổi lớn về tổ chức** (sáp nhập, sa thải, tuyển nhiều).
- **Khi thấy quá nhiều false positive** ở một nhóm user cụ thể
  (ví dụ operator batch chạy đêm).
- **Khi thêm event type mới** (feature vector cần mở rộng).

### 5.2 — Cách retrain

```bash
# 1. Extract dữ liệu qua normalizer (bảng event_logs).
PGPASSWORD=... psql -c "COPY (
    SELECT user_id, event_type, action, resource, timestamp
    FROM event_logs
    WHERE timestamp > NOW() - INTERVAL '6 months'
) TO '/tmp/my_events.csv' WITH CSV HEADER;"

# 2. (Tùy chọn) Thêm CERT r4.2 vào nếu bạn có < 100k events.
# Nếu không thì chỉ dùng dữ liệu của bạn.

# 3. Chạy training pipeline:
python src/ml/services/ueba_ml/pipelines/preprocess.py \
    --input /tmp/my_events.csv \
    --output artifacts/my_features.parquet

python src/ml/services/ueba_ml/pipelines/train.py \
    --features artifacts/my_features.parquet \
    --output src/ml/weights/ocsvm_my_org.joblib \
    --nu 0.005

# 4. Cập nhật deployed model:
UPDATE model_artifacts
SET artifact_path = 'src/ml/weights/ocsvm_my_org.joblib',
    training_config_json = jsonb_build_object('nu', 0.005, 'kernel', 'rbf', 'gamma', 'scale'),
    metrics_json = jsonb_build_object('train_auc', 0.97, 'train_f1', 0.85)
WHERE model_version = 'ocsvm-my-org-v1';
INSERT INTO model_artifacts (model_version, artifact_path, ...) VALUES (...);
```

### 5.3 — A/B testing một model mới

Để roll out model mới mà không gián đoạn production:

1. Train `ocsvm-my-org-v1` trên `my_events.csv`.
2. Load nó như một instance `DeployedOcsvmModel` riêng trong side-by-side
   scorer (chưa implement; sẽ cần config flag để chọn model mỗi
   request).
3. So sánh phân phối `risk_score` cho cùng user qua cả hai model trong
   vài ngày.
4. Promote bằng cách cập nhật row `model_artifacts`.

Hiện tại bạn có thể retrain offline và thay artifact trong maintenance
window.

---

## 6. Evaluation

### 6.1 — Metrics trên CERT r4.2 test set

(Số mẫu từ lần train gốc; số thật phụ thuộc vào test split.)

| Metric | Giá trị |
|---|---|
| Train AUC | 0.98 |
| Test AUC | 0.92 |
| Precision @ top 1% | 0.85 |
| Recall @ top 1% | 0.78 |

### 6.2 — Phân tích false positive

Nguồn false positive phổ biến (trong CERT):
- **System administrators** (IT) — nhiều USB, logon mọi giờ.
- **On-call engineers** — logon lúc 2h để fix sự cố.
- **Sales / road warriors** — logon từ nhiều device, nhiều thành phố.

Biện pháp giảm thiểu:
- Đánh alert là `false_positive` từ admin UI → cung cấp feedback cho
  lần train sau.
- Whitelist user / role cụ thể khỏi scoring (tính năng tương lai).
- Điều chỉnh `ML_SCORING_ALERT_MIN_RISK` cho từng user (tương lai).

### 6.3 — Confusion matrix trên CERT r4.2 test month

(Xấp xỉ; chạy `bash src/ml/scripts/evaluate.sh` để có số chính xác.)

| | Predicted normal | Predicted anomaly |
|---|---|---|
| **Actually normal** | ~99,500 (TN) | ~50 (FP) |
| **Actually anomaly** | ~3 (FN) | ~12 (TP) |

- Precision: 12 / (12 + 50) = 19% (thấp — expected cho one-class với 0.5% nu)
- Recall: 12 / (12 + 3) = 80% (tốt — bắt được hầu hết attacks)
- Cho UEBA, **high recall** quan trọng hơn precision. Analyst thà triaged
  50 false alert còn hơn bỏ sót 3 attack thật.

## 8. Tài liệu tham khảo

- Schölkopf, B., Platt, J. C., Shawe-Taylor, J., Smola, A. J., &
  Williamson, R. C. (2001). "Estimating the support of a
  high-dimensional distribution." *Neural computation*, 13(7).
- CERT Insider Threat Dataset (r4.2) — Carnegie Mellon University,
  Software Engineering Institute.
  https://insights.sei.cmu.edu/library/insider-threat-test-dataset/
- scikit-learn OneClassSVM:
  https://scikit-learn.org/stable/modules/generated/sklearn.svm.OneClassSVM.html
- Tax, D. M. J. (2001). "One-class classification." PhD thesis.
