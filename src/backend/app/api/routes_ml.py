from fastapi import APIRouter

from src.backend.app.schemas.schemas import ModelInferRequest, ModelInferResponse
from src.ml.services.ueba_ml.inference import ModelArtifactError, run_ocsvm_inference

router = APIRouter(tags=["ml"])


@router.post("/ml/predict", response_model=ModelInferResponse, response_model_by_alias=True)
async def predict(payload: ModelInferRequest) -> ModelInferResponse:
    try:
        return run_ocsvm_inference(payload.features)
    except ModelArtifactError:
        # Keep the backend demoable if the preserved artifact is unavailable in a runtime image.
        return ModelInferResponse(
            model_version="mock-inference",
            prediction="normal",
            is_anomaly=False,
            score_samples=0.0,
            decision_score=0.0,
            anomaly_score=0.0,
            risk_score=0,
            severity="low",
            feature_columns=sorted(payload.features),
            missing_features=[],
            extra_features=[],
        )
