from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray

from src.config import settings
from src.models.schemas import ModelInferResponse, ModelMetricsResponse, Severity

logger = logging.getLogger(__name__)

MAX_MODEL_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB limit


@runtime_checkable
class OcsvmPipeline(Protocol):
    def score_samples(self, data: pd.DataFrame) -> NDArray[np.float64]:
        ...

    def decision_function(self, data: pd.DataFrame) -> NDArray[np.float64]:
        ...

    def predict(self, data: pd.DataFrame) -> NDArray[np.signedinteger]:
        ...


@dataclass(frozen=True, slots=True)
class DeployedOcsvmModel:
    pipeline: OcsvmPipeline
    feature_columns: tuple[str, ...]
    nu: float
    kernel: str
    gamma: str
    max_benign_train: int


class ModelArtifactError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def run_ocsvm_inference(features: dict[str, float]) -> ModelInferResponse:
    deployed = get_deployed_ocsvm_model()
    frame = _feature_frame(features, deployed.feature_columns)

    score_samples = float(deployed.pipeline.score_samples(frame)[0])
    decision_score = float(deployed.pipeline.decision_function(frame)[0])
    prediction_value = int(deployed.pipeline.predict(frame)[0])
    is_anomaly = prediction_value == -1
    anomaly_score = -score_samples
    risk_score = _risk_score(decision_score, is_anomaly)

    feature_column_set = set(deployed.feature_columns)
    provided = set(features)
    return ModelInferResponse(
        model_version=settings.ocsvm_model_version,
        prediction="anomaly" if is_anomaly else "normal",
        is_anomaly=is_anomaly,
        score_samples=score_samples,
        decision_score=decision_score,
        anomaly_score=anomaly_score,
        risk_score=risk_score,
        severity=_severity(risk_score),
        feature_columns=list(deployed.feature_columns),
        missing_features=[col for col in deployed.feature_columns if col not in provided],
        extra_features=sorted(provided - feature_column_set),
    )


def get_ocsvm_metrics() -> ModelMetricsResponse:
    deployed = get_deployed_ocsvm_model()
    return ModelMetricsResponse(
        model_version=settings.ocsvm_model_version,
        algorithm="OneClassSVM",
        kernel=deployed.kernel,
        gamma=deployed.gamma,
        nu=deployed.nu,
        max_benign_train=deployed.max_benign_train,
        feature_columns=list(deployed.feature_columns),
    )


@lru_cache(maxsize=1)
def get_deployed_ocsvm_model() -> DeployedOcsvmModel:
    model_path = _model_path()
    if not model_path.exists():
        raise ModelArtifactError(f"Model artifact not found: {model_path}")

    file_size = model_path.stat().st_size
    if file_size > MAX_MODEL_SIZE_BYTES:
        raise ModelArtifactError(
            f"Model artifact too large ({file_size / 1024 / 1024:.1f} MB). "
            f"Maximum allowed: {MAX_MODEL_SIZE_BYTES / 1024 / 1024:.0f} MB"
        )

    if file_size == 0:
        raise ModelArtifactError("Model artifact is empty (0 bytes)")

    logger.info("Loading OCSVM model from %s (%.1f MB)", model_path, file_size / 1024 / 1024)

    try:
        payload = joblib.load(model_path)
    except Exception as exc:
        raise ModelArtifactError(f"Failed to load model artifact (corrupted file): {exc}") from exc

    if not isinstance(payload, dict):
        raise ModelArtifactError("OCSVM artifact must be a dictionary payload")

    feature_columns = payload.get("feature_cols")
    model = payload.get("model")
    if not isinstance(feature_columns, list) or not all(
        isinstance(col, str) for col in feature_columns
    ):
        raise ModelArtifactError("OCSVM artifact is missing string feature_cols")
    if not isinstance(model, OcsvmPipeline):
        raise ModelArtifactError("OCSVM artifact model is missing inference methods")

    return DeployedOcsvmModel(
        pipeline=model,
        feature_columns=tuple(feature_columns),
        nu=float(payload.get("nu", 0.0)),
        kernel=str(payload.get("kernel", "")),
        gamma=str(payload.get("gamma", "")),
        max_benign_train=int(payload.get("max_benign_train", 0)),
    )


def _model_path() -> Path:
    configured = Path(settings.ocsvm_model_path)
    if configured.is_absolute():
        return configured
    return Path.cwd() / configured


def _feature_frame(features: dict[str, float], columns: tuple[str, ...]) -> pd.DataFrame:
    missing_cols: list[str] = []
    row: dict[str, float] = {}
    for column in columns:
        if column in features:
            row[column] = float(features[column])
        else:
            row[column] = 0.0
            missing_cols.append(column)

    if missing_cols:
        logger.warning(
            "Missing %d features for inference, using 0.0 as default: %s",
            len(missing_cols),
            missing_cols,
        )

    return pd.DataFrame([row], columns=list(columns))


def _risk_score(decision_score: float, is_anomaly: bool) -> int:
    if is_anomaly:
        anomaly_strength = min(abs(decision_score), 1.0)
        return min(100, 60 + round(anomaly_strength * 40))

    normal_margin = min(max(decision_score, 0.0), 1.0)
    return max(0, round((1.0 - normal_margin) * 30))


def _severity(risk_score: int) -> Severity:
    if risk_score <= 30:
        return "low"
    if risk_score <= 60:
        return "medium"
    if risk_score <= 80:
        return "high"
    return "critical"
