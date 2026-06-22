import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if __name__ == "__main__":
    VENV_ROOT = REPO_ROOT / ".venv"
    VENV_PYTHON = VENV_ROOT / "bin" / "python"
    if VENV_PYTHON.exists() and Path(sys.prefix).resolve() != VENV_ROOT.resolve():
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


def test_ocsvm_inference_uses_deployed_joblib_model() -> None:
    from src.backend.app.config import settings
    from src.ml.services.ueba_ml import inference

    inference.get_deployed_ocsvm_model.cache_clear()

    features = {
        "logon_count": 4.0,
        "logon_after_hours_count": 1.0,
        "email_size_sum": 18400.0,
        "http_count": 24.0,
    }

    result = inference.run_ocsvm_inference(features)

    assert result.model_version == settings.ocsvm_model_version
    assert result.prediction in {"normal", "anomaly"}
    assert 0 <= result.risk_score <= 100
    assert "logon_count" in result.feature_columns
    assert "email_size_sum" not in result.missing_features


def test_ocsvm_metrics_exposes_feature_schema() -> None:
    from src.backend.app.config import settings
    from src.ml.services.ueba_ml import inference

    inference.get_deployed_ocsvm_model.cache_clear()

    metrics = inference.get_ocsvm_metrics()

    assert metrics.model_version == settings.ocsvm_model_version
    assert metrics.algorithm == "OneClassSVM"
    assert metrics.kernel == "rbf"
    assert metrics.nu == 0.005
    assert len(metrics.feature_columns) == 20


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
