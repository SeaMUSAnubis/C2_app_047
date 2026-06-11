#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Callable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/c2_app_047_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/c2_app_047_cache")
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


DATE_FORMAT = "%m/%d/%Y %H:%M:%S"
WORK_START_HOUR = 7
WORK_END_HOUR = 18
TOP_CORR_FEATURES = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chunked CERT r4.2 preprocessing and EDA for UEBA iForest features."
    )
    parser.add_argument(
        "--input-dir",
        default="data/raw/cert-r4.2",
        help="Raw CERT r4.2 data directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/preprocessing",
        help="Directory for processed feature files and figures.",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory for generated markdown reports.",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=250_000,
        help="Rows per chunk for large CSV files.",
    )
    parser.add_argument(
        "--partial-flush",
        type=int,
        default=12,
        help="Number of grouped chunks to combine at a time.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress after this many chunks per file.",
    )
    return parser.parse_args()


def file_size_mb(path: Path) -> float:
    return round(path.stat().st_size / (1024 * 1024), 2) if path.exists() else 0.0


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numeric_numerator = pd.to_numeric(numerator, errors="coerce").astype("float64")
    numeric_denominator = pd.to_numeric(denominator, errors="coerce").astype("float64")
    result = numeric_numerator / numeric_denominator.mask(numeric_denominator == 0)
    return result.fillna(0.0)


def combine_sum(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames)
    return combined.groupby(level=[0, 1], sort=False).sum(numeric_only=True)


def append_partial(
    partials: list[pd.DataFrame], grouped: pd.DataFrame, flush_every: int
) -> None:
    if grouped.empty:
        return
    partials.append(grouped)
    if len(partials) >= flush_every:
        merged = combine_sum(partials)
        partials.clear()
        partials.append(merged)


def base_event_frame(chunk: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    stats: dict[str, object] = {"rows": len(chunk), "bad_date_rows": 0}
    dt = pd.to_datetime(chunk["date"], format=DATE_FORMAT, errors="coerce")
    valid = dt.notna() & chunk["user"].notna()
    stats["bad_date_rows"] = int((~dt.notna()).sum())
    if not valid.any():
        return pd.DataFrame(), stats

    chunk = chunk.loc[valid].copy()
    dt = dt.loc[valid]
    chunk["date_key"] = dt.dt.strftime("%Y-%m-%d")
    chunk["hour"] = dt.dt.hour.astype("int16")
    chunk["weekday"] = dt.dt.weekday.astype("int16")
    chunk["is_weekend"] = chunk["weekday"] >= 5
    chunk["is_after_hours"] = (
        (chunk["hour"] < WORK_START_HOUR)
        | (chunk["hour"] >= WORK_END_HOUR)
        | chunk["is_weekend"]
    )
    stats["min_timestamp"] = dt.min()
    stats["max_timestamp"] = dt.max()
    return chunk, stats


def count_addresses(series: pd.Series) -> pd.Series:
    values = series.fillna("").astype(str).str.strip()
    non_empty = values.ne("")
    counts = values.str.count(";") + 1
    return counts.where(non_empty, 0).astype("int32")


def count_external_addresses(series: pd.Series) -> pd.Series:
    values = series.fillna("").astype(str).str.lower().str.strip()
    total = count_addresses(values)
    internal = values.str.count("@dtaa.com").astype("int32")
    return (total - internal).clip(lower=0)


def aggregate_logon(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk["logon_event_count"] = 1
    chunk["logon_logon_count"] = chunk["activity"].eq("Logon").astype("int16")
    chunk["logon_logoff_count"] = chunk["activity"].eq("Logoff").astype("int16")
    chunk["logon_after_hours_count"] = chunk["is_after_hours"].astype("int16")
    chunk["logon_weekend_count"] = chunk["is_weekend"].astype("int16")
    chunk["logon_hour_sum"] = chunk["hour"].astype("int32")
    if "pc" in chunk.columns:
        chunk["logon_pc_variety_score"] = chunk["pc"].fillna("").ne("").astype("int16")
    else:
        chunk["logon_pc_variety_score"] = 0
    return chunk.groupby(["user", "date_key"]).agg(
        {
            "logon_event_count": "sum",
            "logon_logon_count": "sum",
            "logon_logoff_count": "sum",
            "logon_after_hours_count": "sum",
            "logon_weekend_count": "sum",
            "logon_hour_sum": "sum",
            "logon_pc_variety_score": "sum",
        }
    )


def aggregate_device(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk["device_event_count"] = 1
    chunk["device_connect_count"] = chunk["activity"].eq("Connect").astype("int16")
    chunk["device_disconnect_count"] = chunk["activity"].eq("Disconnect").astype("int16")
    chunk["device_after_hours_count"] = chunk["is_after_hours"].astype("int16")
    chunk["device_weekend_count"] = chunk["is_weekend"].astype("int16")
    chunk["device_hour_sum"] = chunk["hour"].astype("int32")
    return chunk.groupby(["user", "date_key"]).agg(
        {
            "device_event_count": "sum",
            "device_connect_count": "sum",
            "device_disconnect_count": "sum",
            "device_after_hours_count": "sum",
            "device_weekend_count": "sum",
            "device_hour_sum": "sum",
        }
    )


def aggregate_file(chunk: pd.DataFrame) -> pd.DataFrame:
    filename = chunk.get("filename", pd.Series("", index=chunk.index)).fillna("")
    content = chunk.get("content", pd.Series("", index=chunk.index)).fillna("")
    ext = filename.astype(str).str.extract(r"\.([A-Za-z0-9]+)$", expand=False).str.lower()
    chunk["file_event_count"] = 1
    chunk["file_after_hours_count"] = chunk["is_after_hours"].astype("int16")
    chunk["file_weekend_count"] = chunk["is_weekend"].astype("int16")
    chunk["file_hour_sum"] = chunk["hour"].astype("int32")
    chunk["file_doc_count"] = ext.isin(["doc", "docx", "xls", "xlsx", "ppt", "pptx"]).astype(
        "int16"
    )
    chunk["file_pdf_count"] = ext.eq("pdf").astype("int16")
    chunk["file_content_word_sum"] = content.astype(str).str.count(r"\S+").astype("int32")
    return chunk.groupby(["user", "date_key"]).agg(
        {
            "file_event_count": "sum",
            "file_after_hours_count": "sum",
            "file_weekend_count": "sum",
            "file_hour_sum": "sum",
            "file_doc_count": "sum",
            "file_pdf_count": "sum",
            "file_content_word_sum": "sum",
        }
    )


def aggregate_email(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk["email_event_count"] = 1
    chunk["email_after_hours_count"] = chunk["is_after_hours"].astype("int16")
    chunk["email_weekend_count"] = chunk["is_weekend"].astype("int16")
    chunk["email_hour_sum"] = chunk["hour"].astype("int32")
    chunk["email_size_sum"] = pd.to_numeric(chunk.get("size", 0), errors="coerce").fillna(0)
    chunk["email_attachment_sum"] = pd.to_numeric(
        chunk.get("attachments", 0), errors="coerce"
    ).fillna(0)
    chunk["email_recipient_sum"] = 0
    chunk["email_external_recipient_sum"] = 0
    for col in ["to", "cc", "bcc"]:
        if col in chunk.columns:
            chunk["email_recipient_sum"] += count_addresses(chunk[col])
            chunk["email_external_recipient_sum"] += count_external_addresses(chunk[col])
    return chunk.groupby(["user", "date_key"]).agg(
        {
            "email_event_count": "sum",
            "email_after_hours_count": "sum",
            "email_weekend_count": "sum",
            "email_hour_sum": "sum",
            "email_size_sum": "sum",
            "email_attachment_sum": "sum",
            "email_recipient_sum": "sum",
            "email_external_recipient_sum": "sum",
        }
    )


def aggregate_http(chunk: pd.DataFrame) -> pd.DataFrame:
    url = chunk.get("url", pd.Series("", index=chunk.index)).fillna("").astype(str)
    path_depth = (url.str.count("/") - 2).clip(lower=0)
    chunk["http_event_count"] = 1
    chunk["http_after_hours_count"] = chunk["is_after_hours"].astype("int16")
    chunk["http_weekend_count"] = chunk["is_weekend"].astype("int16")
    chunk["http_hour_sum"] = chunk["hour"].astype("int32")
    chunk["http_path_depth_sum"] = path_depth.astype("int32")
    return chunk.groupby(["user", "date_key"]).agg(
        {
            "http_event_count": "sum",
            "http_after_hours_count": "sum",
            "http_weekend_count": "sum",
            "http_hour_sum": "sum",
            "http_path_depth_sum": "sum",
        }
    )


def process_event_file(
    input_dir: Path,
    filename: str,
    usecols: list[str],
    aggregate_fn: Callable[[pd.DataFrame], pd.DataFrame],
    chunksize: int,
    flush_every: int,
    progress_every: int,
) -> tuple[pd.DataFrame, dict[str, object]]:
    path = input_dir / filename
    summary: dict[str, object] = {
        "file": filename,
        "path": str(path),
        "exists": path.exists(),
        "size_mb": file_size_mb(path),
        "rows": 0,
        "bad_date_rows": 0,
        "chunks": 0,
        "min_timestamp": None,
        "max_timestamp": None,
    }
    if not path.exists():
        return pd.DataFrame(), summary

    partials: list[pd.DataFrame] = []
    reader = pd.read_csv(path, usecols=usecols, dtype=str, chunksize=chunksize)
    for chunk in reader:
        summary["chunks"] = int(summary["chunks"]) + 1
        event_chunk, chunk_stats = base_event_frame(chunk)
        summary["rows"] = int(summary["rows"]) + int(chunk_stats["rows"])
        summary["bad_date_rows"] = int(summary["bad_date_rows"]) + int(
            chunk_stats["bad_date_rows"]
        )
        if event_chunk.empty:
            continue
        chunk_min = chunk_stats.get("min_timestamp")
        chunk_max = chunk_stats.get("max_timestamp")
        if chunk_min is not None and not pd.isna(chunk_min):
            current = summary["min_timestamp"]
            summary["min_timestamp"] = chunk_min if current is None else min(current, chunk_min)
        if chunk_max is not None and not pd.isna(chunk_max):
            current = summary["max_timestamp"]
            summary["max_timestamp"] = chunk_max if current is None else max(current, chunk_max)
        append_partial(partials, aggregate_fn(event_chunk), flush_every)
        if progress_every > 0 and int(summary["chunks"]) % progress_every == 0:
            print(
                f"    {filename}: {summary['chunks']:,} chunks, "
                f"{summary['rows']:,} rows read",
                flush=True,
            )

    return combine_sum(partials), summary


def load_ldap_latest(input_dir: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    ldap_dir = input_dir / "LDAP"
    summary: dict[str, object] = {"files": 0, "rows": 0, "exists": ldap_dir.exists()}
    if not ldap_dir.exists():
        return pd.DataFrame(), summary

    frames = []
    for path in sorted(ldap_dir.glob("*.csv")):
        frame = pd.read_csv(path, dtype=str)
        frame["snapshot_month"] = path.stem
        frames.append(frame)
        summary["files"] = int(summary["files"]) + 1
        summary["rows"] = int(summary["rows"]) + len(frame)
    if not frames:
        return pd.DataFrame(), summary

    ldap = pd.concat(frames, ignore_index=True)
    ldap = ldap.sort_values("snapshot_month")
    latest = ldap.drop_duplicates("user_id", keep="last").rename(columns={"user_id": "user"})
    keep_cols = [
        "user",
        "employee_name",
        "email",
        "role",
        "business_unit",
        "functional_unit",
        "department",
        "team",
        "supervisor",
        "snapshot_month",
    ]
    return latest[[col for col in keep_cols if col in latest.columns]], summary


def load_psychometric(input_dir: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    path = input_dir / "psychometric.csv"
    summary = {
        "file": "psychometric.csv",
        "exists": path.exists(),
        "size_mb": file_size_mb(path),
        "rows": 0,
    }
    if not path.exists():
        return pd.DataFrame(), summary
    frame = pd.read_csv(path, dtype={"user_id": str})
    summary["rows"] = len(frame)
    return frame.rename(columns={"user_id": "user"}), summary


def finalize_features(
    event_frames: dict[str, pd.DataFrame], ldap: pd.DataFrame, psychometric: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    non_empty = [frame for frame in event_frames.values() if not frame.empty]
    if not non_empty:
        return pd.DataFrame(), pd.DataFrame(), []

    features = pd.concat(non_empty, axis=1).fillna(0).reset_index()
    features = features.rename(columns={"date_key": "date"})
    count_cols = [col for col in features.columns if col.endswith("_event_count")]
    after_cols = [col for col in features.columns if col.endswith("_after_hours_count")]
    weekend_cols = [col for col in features.columns if col.endswith("_weekend_count")]

    features["total_events"] = features[count_cols].sum(axis=1) if count_cols else 0
    features["after_hours_events"] = features[after_cols].sum(axis=1) if after_cols else 0
    features["weekend_events"] = features[weekend_cols].sum(axis=1) if weekend_cols else 0
    features["after_hours_ratio"] = safe_divide(
        features["after_hours_events"], features["total_events"]
    )
    features["weekend_ratio"] = safe_divide(features["weekend_events"], features["total_events"])

    avg_specs = [
        ("logon_avg_hour", "logon_hour_sum", "logon_event_count"),
        ("device_avg_hour", "device_hour_sum", "device_event_count"),
        ("file_avg_hour", "file_hour_sum", "file_event_count"),
        ("email_avg_hour", "email_hour_sum", "email_event_count"),
        ("http_avg_hour", "http_hour_sum", "http_event_count"),
        ("file_avg_content_words", "file_content_word_sum", "file_event_count"),
        ("email_avg_size", "email_size_sum", "email_event_count"),
        ("email_attachment_rate", "email_attachment_sum", "email_event_count"),
        ("email_recipient_rate", "email_recipient_sum", "email_event_count"),
        (
            "email_external_recipient_rate",
            "email_external_recipient_sum",
            "email_event_count",
        ),
        ("http_avg_path_depth", "http_path_depth_sum", "http_event_count"),
    ]
    for target, numerator, denominator in avg_specs:
        if numerator in features.columns and denominator in features.columns:
            features[target] = safe_divide(features[numerator], features[denominator])
        else:
            features[target] = 0.0

    if "device_connect_count" in features.columns and "file_event_count" in features.columns:
        features["file_per_device_connect"] = safe_divide(
            features["file_event_count"], features["device_connect_count"]
        )
    else:
        features["file_per_device_connect"] = 0.0

    features["date"] = pd.to_datetime(features["date"], errors="coerce")
    features["day_of_week"] = features["date"].dt.weekday.fillna(0).astype("int16")
    features["month"] = features["date"].dt.month.fillna(0).astype("int16")
    features["is_weekend_day"] = features["day_of_week"].isin([5, 6]).astype("int16")
    features["date"] = features["date"].dt.strftime("%Y-%m-%d")

    zscore_base_cols = [
        col
        for col in [
            "total_events",
            "after_hours_events",
            "weekend_events",
            "logon_event_count",
            "device_event_count",
            "file_event_count",
            "email_event_count",
            "http_event_count",
            "email_attachment_sum",
            "email_external_recipient_sum",
            "file_per_device_connect",
        ]
        if col in features.columns
    ]
    for col in zscore_base_cols:
        values = pd.to_numeric(features[col], errors="coerce").astype("float64")
        mean = values.groupby(features["user"]).transform("mean")
        std = values.groupby(features["user"]).transform("std")
        features[f"{col}_user_zscore"] = ((values - mean) / std.mask(std == 0)).fillna(0.0)

    if not ldap.empty:
        features = features.merge(ldap, on="user", how="left")
    if not psychometric.empty:
        psych_cols = ["user", "O", "C", "E", "A", "N"]
        features = features.merge(
            psychometric[[col for col in psych_cols if col in psychometric.columns]],
            on="user",
            how="left",
        )

    for col in ["role", "department", "functional_unit", "team"]:
        if col in features.columns:
            normalized = features[col].fillna("unknown")
            freq = normalized.value_counts(normalize=True)
            features[f"{col}_frequency"] = normalized.map(freq).fillna(0.0)

    for col in ["O", "C", "E", "A", "N"]:
        if col in features.columns:
            features[col] = pd.to_numeric(features[col], errors="coerce")
            features[col] = features[col].fillna(features[col].median()).fillna(0.0)

    id_cols = {"user", "date"}
    raw_categorical_cols = {
        "employee_name",
        "email",
        "role",
        "business_unit",
        "functional_unit",
        "department",
        "team",
        "supervisor",
        "snapshot_month",
    }
    drop_intermediate = {
        col
        for col in features.columns
        if col.endswith("_hour_sum")
        or col.endswith("_size_sum")
        or col.endswith("_content_word_sum")
        or col.endswith("_path_depth_sum")
    }
    numeric_features = []
    for col in features.columns:
        if col in id_cols or col in raw_categorical_cols or col in drop_intermediate:
            continue
        if pd.api.types.is_numeric_dtype(features[col]):
            numeric_features.append(col)

    matrix = features[["user", "date"] + numeric_features].copy()
    matrix[numeric_features] = matrix[numeric_features].replace([math.inf, -math.inf], 0)
    matrix[numeric_features] = matrix[numeric_features].fillna(0.0)
    return features, matrix, numeric_features


def write_visualizations(features: pd.DataFrame, matrix: pd.DataFrame, output_dir: Path) -> list[str]:
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    if features.empty:
        return outputs

    count_cols = [col for col in features.columns if col.endswith("_event_count")]
    if count_cols:
        totals = features[count_cols].sum().sort_values(ascending=False)
        plt.figure(figsize=(8, 5))
        totals.plot(kind="bar", color="#2F6B8F")
        plt.title("Event Volume by Source")
        plt.ylabel("Rows")
        plt.xticks(rotation=35, ha="right")
        plt.tight_layout()
        path = figure_dir / "event_volume_by_source.png"
        plt.savefig(path, dpi=150)
        plt.close()
        outputs.append(str(path))

        daily = features.groupby("date")[count_cols].sum()
        plt.figure(figsize=(11, 5))
        daily.sum(axis=1).plot(color="#0F766E", linewidth=1.5)
        plt.title("Daily Event Volume")
        plt.ylabel("Events")
        plt.xlabel("Date")
        plt.tight_layout()
        path = figure_dir / "daily_event_volume.png"
        plt.savefig(path, dpi=150)
        plt.close()
        outputs.append(str(path))

    if "total_events" in features.columns:
        top_users = features.groupby("user")["total_events"].sum().nlargest(15)
        plt.figure(figsize=(10, 5))
        top_users.sort_values().plot(kind="barh", color="#A15C38")
        plt.title("Top Users by Event Volume")
        plt.xlabel("Events")
        plt.tight_layout()
        path = figure_dir / "top_users_by_event_volume.png"
        plt.savefig(path, dpi=150)
        plt.close()
        outputs.append(str(path))

    if "after_hours_ratio" in features.columns:
        plt.figure(figsize=(8, 5))
        features["after_hours_ratio"].clip(0, 1).plot(kind="hist", bins=30, color="#6B7280")
        plt.title("After-hours Activity Ratio Distribution")
        plt.xlabel("After-hours ratio")
        plt.tight_layout()
        path = figure_dir / "after_hours_ratio_distribution.png"
        plt.savefig(path, dpi=150)
        plt.close()
        outputs.append(str(path))

    numeric = matrix.drop(columns=["user", "date"], errors="ignore")
    if not numeric.empty and len(numeric) > 2:
        variances = numeric.var(numeric_only=True).sort_values(ascending=False)
        selected = variances.head(TOP_CORR_FEATURES).index.tolist()
        corr = numeric[selected].corr().fillna(0)
        plt.figure(figsize=(11, 9))
        plt.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
        plt.colorbar(label="Correlation")
        plt.xticks(range(len(selected)), selected, rotation=90, fontsize=7)
        plt.yticks(range(len(selected)), selected, fontsize=7)
        plt.title("Feature Correlation Heatmap")
        plt.tight_layout()
        path = figure_dir / "feature_correlation_heatmap.png"
        plt.savefig(path, dpi=150)
        plt.close()
        outputs.append(str(path))

    return outputs


def format_timestamp(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return str(value)


def write_report(
    report_path: Path,
    input_dir: Path,
    output_dir: Path,
    source_summaries: dict[str, dict[str, object]],
    ldap_summary: dict[str, object],
    psych_summary: dict[str, object],
    features: pd.DataFrame,
    matrix: pd.DataFrame,
    numeric_features: list[str],
    figure_paths: list[str],
    chunksize: int,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    count_cols = [col for col in features.columns if col.endswith("_event_count")]
    total_events = int(features[count_cols].sum().sum()) if count_cols and not features.empty else 0
    unique_users = int(features["user"].nunique()) if not features.empty else 0
    date_min = features["date"].min() if not features.empty else "n/a"
    date_max = features["date"].max() if not features.empty else "n/a"

    source_lines = []
    for name, summary in source_summaries.items():
        source_lines.append(
            "| {name} | {exists} | {rows:,} | {chunks:,} | {size_mb} | {bad:,} | {start} | {end} |".format(
                name=name,
                exists="yes" if summary.get("exists") else "no",
                rows=int(summary.get("rows", 0)),
                chunks=int(summary.get("chunks", 0)),
                size_mb=summary.get("size_mb", 0),
                bad=int(summary.get("bad_date_rows", 0)),
                start=format_timestamp(summary.get("min_timestamp")),
                end=format_timestamp(summary.get("max_timestamp")),
            )
        )

    feature_preview = "\n".join(f"- `{col}`" for col in numeric_features[:80])
    figure_lines = "\n".join(f"- `{Path(path)}`" for path in figure_paths) or "- n/a"

    report = f"""# Báo cáo tiền xử lý dữ liệu UEBA

## Ngữ cảnh đề tài

Các tài liệu đã đọc gồm `docs/PRD.md`, `docs/BRIEF.md`,
`docs/UEBA_REQUIREMENTS.md`, `data/raw/cert-r4.2/readme.txt` và schema mẫu trong
`data/sample/cert-r4.2-small/`. Đề tài là UEBA Endpoint Monitoring cho bài toán insider
threat/account compromise trên CERT r4.2. Các nguồn tín hiệu bắt buộc gồm
`logon`, `device`, `file`, `http`, `email`, LDAP snapshots và psychometric
attributes nếu có.

Mục tiêu tiền xử lý là gom log rời rạc thành bảng hành vi theo ngày của từng
user (`user + date`), sau đó xuất ma trận số có thể đưa trực tiếp vào mô hình
Isolation Forest.

## Cấu hình chạy

- Thư mục dữ liệu vào: `{input_dir}`
- Thư mục output: `{output_dir}`
- Chunk size: `{chunksize:,}` dòng
- Giả định giờ làm việc: `{WORK_START_HOUR}:00 <= hour < {WORK_END_HOUR}:00`,
  từ thứ Hai đến thứ Sáu
- Mức aggregate: `user + date`

## Tổng quan xử lý nguồn dữ liệu

| Nguồn | Tồn tại | Dòng đã đọc | Số chunk | Dung lượng MB | Dòng lỗi ngày | Timestamp nhỏ nhất | Timestamp lớn nhất |
|---|---:|---:|---:|---:|---:|---|---|
{chr(10).join(source_lines)}

LDAP snapshots: {ldap_summary.get("files", 0)} file, {ldap_summary.get("rows", 0):,} dòng.

Psychometric: {psych_summary.get("rows", 0):,} dòng.

## Kết quả output

- Số dòng user-day: {len(features):,}
- Số user duy nhất: {unique_users:,}
- Khoảng ngày: `{date_min}` đến `{date_max}`
- Tổng event đã biểu diễn trong aggregate: {total_events:,}
- Số feature số cho iForest: {len(numeric_features):,}
- Feature đầy đủ, dễ đọc: `{output_dir / "user_day_features.csv"}`
- Ma trận số cho iForest: `{output_dir / "iforest_feature_matrix.csv"}`
- Danh sách cột feature: `{output_dir / "iforest_feature_columns.json"}`

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

{feature_preview}

## Biểu đồ đã tạo

{figure_lines}

## Ghi chú cho Isolation Forest

Dùng `iforest_feature_matrix.csv` làm dữ liệu đầu vào cho model. Giữ `user` và
`date` làm cột định danh, còn các cột còn lại là numeric feature để train
Isolation Forest. Pipeline hiện tại chưa train model; nó chuẩn bị dữ liệu và
biểu đồ chẩn đoán trước bước huấn luyện.

Với dữ liệu gốc, các CSV lớn không được load toàn bộ vào RAM. Mỗi nguồn được đọc
bằng `pandas.read_csv(..., chunksize={chunksize:,})`, aggregate ngay về
`user-date`, rồi mới merge thành bảng feature cuối.
"""
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    reports_dir = Path(args.reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    event_specs = {
        "logon": (
            "logon.csv",
            ["id", "date", "user", "pc", "activity"],
            aggregate_logon,
        ),
        "device": (
            "device.csv",
            ["id", "date", "user", "pc", "activity"],
            aggregate_device,
        ),
        "file": (
            "file.csv",
            ["id", "date", "user", "pc", "filename", "content"],
            aggregate_file,
        ),
        "email": (
            "email.csv",
            ["id", "date", "user", "pc", "to", "cc", "bcc", "size", "attachments"],
            aggregate_email,
        ),
        "http": (
            "http.csv",
            ["id", "date", "user", "pc", "url"],
            aggregate_http,
        ),
    }

    event_frames: dict[str, pd.DataFrame] = {}
    source_summaries: dict[str, dict[str, object]] = {}
    for source, (filename, usecols, aggregate_fn) in event_specs.items():
        print(f"Processing {filename} with chunksize={args.chunksize} ...", flush=True)
        frame, summary = process_event_file(
            input_dir,
            filename,
            usecols,
            aggregate_fn,
            args.chunksize,
            args.partial_flush,
            args.progress_every,
        )
        event_frames[source] = frame
        source_summaries[source] = summary
        print(
            f"  rows={summary.get('rows', 0):,}, chunks={summary.get('chunks', 0):,}, "
            f"aggregates={len(frame):,}",
            flush=True,
        )

    ldap, ldap_summary = load_ldap_latest(input_dir)
    psychometric, psych_summary = load_psychometric(input_dir)
    features, matrix, numeric_features = finalize_features(event_frames, ldap, psychometric)

    features_path = output_dir / "user_day_features.csv"
    matrix_path = output_dir / "iforest_feature_matrix.csv"
    columns_path = output_dir / "iforest_feature_columns.json"
    summary_path = output_dir / "source_summary.json"

    features.to_csv(features_path, index=False)
    matrix.to_csv(matrix_path, index=False)
    columns_path.write_text(json.dumps(numeric_features, indent=2), encoding="utf-8")
    summary_path.write_text(
        json.dumps(
            {
                "sources": {
                    name: {
                        key: format_timestamp(value)
                        if key in {"min_timestamp", "max_timestamp"}
                        else value
                        for key, value in summary.items()
                    }
                    for name, summary in source_summaries.items()
                },
                "ldap": ldap_summary,
                "psychometric": psych_summary,
                "rows": len(features),
                "numeric_features": len(numeric_features),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    figure_paths = write_visualizations(features, matrix, output_dir)
    write_report(
        reports_dir / "preprocessing_report.md",
        input_dir,
        output_dir,
        source_summaries,
        ldap_summary,
        psych_summary,
        features,
        matrix,
        numeric_features,
        figure_paths,
        args.chunksize,
    )

    print(f"Wrote {features_path}")
    print(f"Wrote {matrix_path}")
    print(f"Wrote {reports_dir / 'preprocessing_report.md'}")


if __name__ == "__main__":
    main()
