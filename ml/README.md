# UEBA ML

Thư mục này chứa source code preprocessing, feature engineering, training và scoring cho UEBA Endpoint Monitoring.

## Pipelines

- `ueba_ml/pipelines/preprocess.py`: đọc CERT r4.2-style logs theo chunk, aggregate về `user + date`, sinh feature matrix và EDA figures.
- `ueba_ml/pipelines/train.py`: train Isolation Forest từ feature matrix, sinh model artifact, anomaly scores, feature lift và training report.

## Chạy preprocessing

Sample nhỏ:

```bash
python ml/ueba_ml/pipelines/preprocess.py --input-dir data/sample/cert-r4.2-small
```

Raw dataset:

```bash
python ml/ueba_ml/pipelines/preprocess.py --input-dir data/raw/cert-r4.2 --chunksize 250000
```

Output:

- `artifacts/preprocessing/user_day_features.csv`
- `artifacts/preprocessing/iforest_feature_matrix.csv`
- `artifacts/preprocessing/iforest_feature_columns.json`
- `artifacts/preprocessing/source_summary.json`
- `artifacts/preprocessing/figures/*.png`
- `reports/preprocessing_report.md`

## Chạy training

```bash
python ml/ueba_ml/pipelines/train.py
```

Output:

- `artifacts/models/iforest_model.joblib`
- `artifacts/models/iforest_metadata.json`
- `artifacts/models/iforest_anomaly_scores.csv`
- `artifacts/models/iforest_top_anomalies.csv`
- `artifacts/evaluation/iforest_feature_lift.csv`
- `reports/figures/model/iforest/*.png`
- `reports/iforest_training_report.md`

## Quy ước

- Source code ML nằm trong `ml/ueba_ml/`.
- Dữ liệu raw/sample nằm trong `data/`.
- Output máy sinh ra nằm trong `artifacts/`.
- Báo cáo cho người đọc nằm trong `reports/`.
- Notebook chỉ dùng để exploration và đặt trong `ml/notebooks/`.
