#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/c2_app_047_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/c2_app_047_cache")
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DEFAULT_INPUT = "artifacts/preprocessing/iforest_feature_matrix.csv"
ID_COLUMNS = ["user", "date"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train Isolation Forest anomaly detector on UEBA user-day features."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Preprocessed iForest matrix CSV.")
    parser.add_argument(
        "--models-dir",
        default="artifacts/models",
        help="Directory to save model artifacts and scoring outputs.",
    )
    parser.add_argument(
        "--evaluation-dir",
        default="artifacts/evaluation",
        help="Directory to save evaluation tables.",
    )
    parser.add_argument("--reports-dir", default="reports", help="Directory to save reports.")
    parser.add_argument(
        "--figures-dir",
        default="reports/figures/model/iforest",
        help="Directory to save model diagnostic figures.",
    )
    parser.add_argument("--contamination", type=float, default=0.02, help="Expected anomaly rate.")
    parser.add_argument("--n-estimators", type=int, default=300, help="Isolation Forest trees.")
    parser.add_argument(
        "--max-samples",
        default="10000",
        help="Rows sampled per tree. Use integer or 'auto'.",
    )
    parser.add_argument("--random-state", type=int, default=42, help="Random seed.")
    parser.add_argument("--top-n", type=int, default=200, help="Rows to save in top anomalies CSV.")
    return parser.parse_args()


def parse_max_samples(value: str) -> str | int:
    if value == "auto":
        return value
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("--max-samples must be positive or 'auto'")
    return parsed


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_numeric_matrix(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    matrix = frame[feature_columns].apply(pd.to_numeric, errors="coerce")
    matrix = matrix.replace([np.inf, -np.inf], np.nan)
    return matrix


def top_driver_text(
    raw_row: pd.Series, scaled_row: np.ndarray, feature_columns: list[str], top_k: int = 5
) -> str:
    if len(feature_columns) == 0:
        return ""
    top_indices = np.argsort(np.abs(scaled_row))[-top_k:][::-1]
    parts = []
    for idx in top_indices:
        feature = feature_columns[int(idx)]
        raw_value = raw_row[feature]
        scaled_value = scaled_row[int(idx)]
        if pd.isna(raw_value):
            raw_display = "nan"
        elif isinstance(raw_value, (int, np.integer)):
            raw_display = str(int(raw_value))
        elif isinstance(raw_value, (float, np.floating)):
            raw_display = f"{float(raw_value):.4g}"
        else:
            raw_display = str(raw_value)
        parts.append(f"{feature}={raw_display} (z={scaled_value:.2f})")
    return "; ".join(parts)


def write_score_plots(results: pd.DataFrame, figures_dir: Path) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    plt.figure(figsize=(9, 5))
    results["anomaly_score"].plot(kind="hist", bins=80, color="#2F6B8F")
    threshold = float(results.loc[results["is_anomaly"], "anomaly_score"].min())
    plt.axvline(threshold, color="#B91C1C", linestyle="--", linewidth=1.5, label="threshold")
    plt.title("Isolation Forest Anomaly Score Distribution")
    plt.xlabel("Anomaly score (-score_samples), higher is more anomalous")
    plt.ylabel("User-day rows")
    plt.legend()
    plt.tight_layout()
    path = figures_dir / "iforest_score_distribution.png"
    plt.savefig(path, dpi=150)
    plt.close()
    outputs.append(path)

    daily = results.assign(date=pd.to_datetime(results["date"], errors="coerce"))
    daily_counts = daily.groupby("date")["is_anomaly"].sum()
    if not daily_counts.empty:
        plt.figure(figsize=(11, 5))
        daily_counts.plot(color="#A15C38", linewidth=1.5)
        plt.title("Daily Anomaly Count")
        plt.ylabel("Anomaly user-days")
        plt.xlabel("Date")
        plt.tight_layout()
        path = figures_dir / "iforest_anomalies_by_date.png"
        plt.savefig(path, dpi=150)
        plt.close()
        outputs.append(path)

    top_users = results.groupby("user")["is_anomaly"].sum().sort_values(ascending=False).head(15)
    if not top_users.empty:
        plt.figure(figsize=(10, 5))
        top_users.sort_values().plot(kind="barh", color="#0F766E")
        plt.title("Top Users by Anomaly Count")
        plt.xlabel("Anomaly user-days")
        plt.tight_layout()
        path = figures_dir / "iforest_top_anomaly_users.png"
        plt.savefig(path, dpi=150)
        plt.close()
        outputs.append(path)

    return outputs


def feature_lift_table(
    matrix: pd.DataFrame, results: pd.DataFrame, feature_columns: list[str], top_n: int = 40
) -> pd.DataFrame:
    anomaly_mask = results["is_anomaly"].to_numpy()
    normal_mask = ~anomaly_mask
    if anomaly_mask.sum() == 0 or normal_mask.sum() == 0:
        return pd.DataFrame()

    anomaly_mean = matrix.loc[anomaly_mask, feature_columns].mean()
    normal_mean = matrix.loc[normal_mask, feature_columns].mean()
    overall_std = matrix[feature_columns].std().replace(0, np.nan)
    lift = ((anomaly_mean - normal_mean) / overall_std).replace([np.inf, -np.inf], np.nan)
    table = pd.DataFrame(
        {
            "feature": feature_columns,
            "anomaly_mean": anomaly_mean.reindex(feature_columns).to_numpy(),
            "normal_mean": normal_mean.reindex(feature_columns).to_numpy(),
            "standardized_lift": lift.reindex(feature_columns).to_numpy(),
        }
    )
    table["abs_standardized_lift"] = table["standardized_lift"].abs()
    return table.sort_values("abs_standardized_lift", ascending=False).head(top_n)


def write_report(
    report_path: Path,
    input_path: Path,
    models_dir: Path,
    evaluation_dir: Path,
    metadata: dict[str, object],
    results: pd.DataFrame,
    top_anomalies: pd.DataFrame,
    feature_lift: pd.DataFrame,
    figure_paths: list[Path],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    score = results["anomaly_score"]
    decision = results["decision_score"]
    anomaly_count = int(results["is_anomaly"].sum())
    anomaly_rate = anomaly_count / len(results) if len(results) else 0.0
    threshold = float(results.loc[results["is_anomaly"], "anomaly_score"].min())

    top_users = (
        results.groupby("user")["is_anomaly"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .astype(int)
    )
    top_user_lines = "\n".join(f"- `{user}`: {count}" for user, count in top_users.items())

    top_dates = (
        results.groupby("date")["is_anomaly"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .astype(int)
    )
    top_date_lines = "\n".join(f"- `{date}`: {count}" for date, count in top_dates.items())

    top_anomaly_lines = []
    for _, row in top_anomalies.head(15).iterrows():
        top_anomaly_lines.append(
            "- `{user}` `{date}` score={score:.6f}, decision={decision:.6f}, drivers: {drivers}".format(
                user=row["user"],
                date=row["date"],
                score=row["anomaly_score"],
                decision=row["decision_score"],
                drivers=row["top_feature_drivers"],
            )
        )

    lift_lines = []
    for _, row in feature_lift.head(20).iterrows():
        lift_lines.append(
            "- `{feature}`: anomaly_mean={anom:.4g}, normal_mean={normal:.4g}, lift={lift:.3f}".format(
                feature=row["feature"],
                anom=row["anomaly_mean"],
                normal=row["normal_mean"],
                lift=row["standardized_lift"],
            )
        )

    figure_lines = "\n".join(f"- `{path}`" for path in figure_paths) or "- n/a"

    report = f"""# Báo cáo huấn luyện Isolation Forest

## Mục tiêu

Huấn luyện mô hình Isolation Forest để phát hiện anomaly trên bảng hành vi
`user + date` đã được tạo từ bước tiền xử lý UEBA. Đây là bài toán unsupervised,
vì vậy report tập trung vào cấu hình train, phân phối điểm anomaly, số lượng
record bị gắn cờ và các feature nổi bật ở nhóm anomaly.

## Dữ liệu train

- Input: `{input_path}`
- Số dòng: {metadata["row_count"]:,}
- Số numeric feature: {metadata["feature_count"]:,}
- Số user: {metadata["unique_users"]:,}
- Khoảng ngày: `{metadata["date_min"]}` đến `{metadata["date_max"]}`
- NaN sau khi chuẩn bị matrix: {metadata["nan_cells"]:,}
- Infinite values sau khi chuẩn bị matrix: {metadata["inf_cells"]:,}

## Cấu hình mô hình

- Pipeline: `SimpleImputer(strategy=median) -> StandardScaler -> IsolationForest`
- `n_estimators`: {metadata["n_estimators"]}
- `max_samples`: {metadata["max_samples"]}
- `contamination`: {metadata["contamination"]}
- `random_state`: {metadata["random_state"]}
- `n_jobs`: -1
- Thời gian train + scoring: {metadata["elapsed_seconds"]:.2f} giây
- `sklearn`: {metadata["sklearn_version"]}

## Kết quả scoring

- Số anomaly user-day: {anomaly_count:,}
- Tỷ lệ anomaly: {anomaly_rate:.2%}
- Ngưỡng anomaly score: {threshold:.6f}
- `anomaly_score = -score_samples`; điểm càng cao càng bất thường.
- `decision_score < 0` được gắn nhãn anomaly.

Score distribution:

| Metric | anomaly_score | decision_score |
|---|---:|---:|
| min | {score.min():.6f} | {decision.min():.6f} |
| p05 | {score.quantile(0.05):.6f} | {decision.quantile(0.05):.6f} |
| p50 | {score.quantile(0.50):.6f} | {decision.quantile(0.50):.6f} |
| p95 | {score.quantile(0.95):.6f} | {decision.quantile(0.95):.6f} |
| max | {score.max():.6f} | {decision.max():.6f} |

## Top users có nhiều anomaly

{top_user_lines}

## Top ngày có nhiều anomaly

{top_date_lines}

## Một số anomaly nổi bật

{chr(10).join(top_anomaly_lines)}

## Feature khác biệt nhất giữa anomaly và normal

Các giá trị dưới đây là so sánh trung bình anomaly vs normal, chuẩn hóa theo độ
lệch chuẩn toàn bộ dữ liệu. Đây không phải feature importance nội tại chính xác
của Isolation Forest, nhưng hữu ích để đọc nhanh kiểu hành vi đang bị model gắn
cờ.

{chr(10).join(lift_lines)}

## File đã sinh

- Model artifact: `{models_dir / "iforest_model.joblib"}`
- Metadata: `{models_dir / "iforest_metadata.json"}`
- Toàn bộ score: `{models_dir / "iforest_anomaly_scores.csv"}`
- Top anomaly: `{models_dir / "iforest_top_anomalies.csv"}`
- Feature lift: `{evaluation_dir / "iforest_feature_lift.csv"}`

## Biểu đồ

{figure_lines}

## Lưu ý vận hành

Vì dữ liệu không có nhãn ground truth trong pipeline hiện tại, chưa thể báo cáo
precision/recall/F1. Nên dùng report này để chọn `contamination` và kiểm tra
top anomaly thủ công trước khi tích hợp scoring vào backend/dashboard.
"""
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    args = parse_args()
    start = time.perf_counter()
    input_path = Path(args.input)
    models_dir = Path(args.models_dir)
    evaluation_dir = Path(args.evaluation_dir)
    reports_dir = Path(args.reports_dir)
    figures_dir = Path(args.figures_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    max_samples = parse_max_samples(args.max_samples)
    print(f"Loading {input_path} ...", flush=True)
    data = pd.read_csv(input_path)
    missing_ids = [col for col in ID_COLUMNS if col not in data.columns]
    if missing_ids:
        raise ValueError(f"Missing required ID columns: {missing_ids}")

    feature_columns = [col for col in data.columns if col not in ID_COLUMNS]
    matrix = clean_numeric_matrix(data, feature_columns)
    nan_cells = int(matrix.isna().sum().sum())
    inf_cells = int(np.isinf(matrix.to_numpy(dtype="float64", na_value=np.nan)).sum())

    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "iforest",
                IsolationForest(
                    n_estimators=args.n_estimators,
                    max_samples=max_samples,
                    contamination=args.contamination,
                    random_state=args.random_state,
                    n_jobs=-1,
                    verbose=0,
                ),
            ),
        ]
    )

    print(
        f"Training IsolationForest on {len(matrix):,} rows and {len(feature_columns):,} features ...",
        flush=True,
    )
    pipeline.fit(matrix)
    print("Scoring all rows ...", flush=True)
    score_samples = pipeline.score_samples(matrix)
    decision_scores = pipeline.decision_function(matrix)
    predictions = pipeline.predict(matrix)

    scored = data[ID_COLUMNS].copy()
    scored["_row_position"] = np.arange(len(scored))
    scored["score_samples"] = score_samples
    scored["anomaly_score"] = -score_samples
    scored["decision_score"] = decision_scores
    scored["prediction"] = predictions
    scored["is_anomaly"] = predictions == -1
    results = scored.sort_values("anomaly_score", ascending=False).reset_index(drop=True)

    top_n = min(args.top_n, len(results))
    top_anomalies = results.head(top_n).copy()
    top_positions = top_anomalies["_row_position"].to_numpy()
    transformed_top = pipeline[:-1].transform(matrix.iloc[top_positions])
    raw_top = matrix.iloc[top_positions].reset_index(drop=True)
    top_anomalies["top_feature_drivers"] = [
        top_driver_text(raw_top.iloc[i], transformed_top[i], feature_columns)
        for i in range(len(top_anomalies))
    ]
    top_anomalies = top_anomalies.drop(columns=["_row_position"]).head(top_n)

    feature_lift = feature_lift_table(matrix, scored, feature_columns)
    elapsed = time.perf_counter() - start
    metadata = {
        "trained_at_utc": now_utc(),
        "input_path": str(input_path),
        "row_count": int(len(data)),
        "feature_count": int(len(feature_columns)),
        "feature_columns": feature_columns,
        "id_columns": ID_COLUMNS,
        "unique_users": int(data["user"].nunique()),
        "date_min": str(data["date"].min()),
        "date_max": str(data["date"].max()),
        "nan_cells": nan_cells,
        "inf_cells": inf_cells,
        "n_estimators": args.n_estimators,
        "max_samples": max_samples,
        "contamination": args.contamination,
        "random_state": args.random_state,
        "elapsed_seconds": elapsed,
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "anomaly_count": int(results["is_anomaly"].sum()),
        "anomaly_rate": float(results["is_anomaly"].mean()),
    }

    model_payload = {
        "pipeline": pipeline,
        "feature_columns": feature_columns,
        "id_columns": ID_COLUMNS,
        "metadata": metadata,
    }
    joblib.dump(model_payload, models_dir / "iforest_model.joblib")
    results.drop(columns=["_row_position"]).to_csv(
        models_dir / "iforest_anomaly_scores.csv", index=False
    )
    top_anomalies.to_csv(models_dir / "iforest_top_anomalies.csv", index=False)
    feature_lift.to_csv(evaluation_dir / "iforest_feature_lift.csv", index=False)
    (models_dir / "iforest_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    figure_paths = write_score_plots(results, figures_dir)
    write_report(
        reports_dir / "iforest_training_report.md",
        input_path,
        models_dir,
        evaluation_dir,
        metadata,
        results,
        top_anomalies,
        feature_lift,
        figure_paths,
    )

    print(f"Wrote {models_dir / 'iforest_model.joblib'}")
    print(f"Wrote {models_dir / 'iforest_anomaly_scores.csv'}")
    print(f"Wrote {reports_dir / 'iforest_training_report.md'}")


if __name__ == "__main__":
    main()
