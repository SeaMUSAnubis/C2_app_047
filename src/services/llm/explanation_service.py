import hashlib
import json
import logging
import uuid
import uuid
from datetime import datetime, timezone

from src.models.explanation import AlertExplanationRequest, AlertExplanationResponse
from src.services.llm.client import LLMClient
from src.services.llm.fallback_service import generate_fallback_explanation
from src.services.llm.guardrails import sanitize_input_request, validate_llm_response
from src.services.llm.prompt_builder import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


def compute_evidence_hash(request: AlertExplanationRequest) -> str:
    data = {
        "features": [f.model_dump() for f in request.anomalous_features],
        "baseline": [b.model_dump() for b in request.baseline_comparisons],
        "events": [e.model_dump(mode="json") for e in request.timeline_events],
        "urls": [u.model_dump() for u in request.suspicious_urls],
        "risk_score": request.risk_score,
        "severity": request.severity,
    }
    encoded = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def calculate_confidence(request: AlertExplanationRequest) -> float:
    confidence = 0.25
    if request.anomalous_features:
        confidence += 0.20
    if request.baseline_comparisons:
        confidence += 0.20
    if request.timeline_events:
        confidence += 0.15
    if request.suspicious_urls:
        confidence += 0.10
    if request.model_version:
        confidence += 0.05
    if request.main_reason:
        confidence += 0.05
    
    return min(confidence, 0.95)


def generate_explanation(request: AlertExplanationRequest) -> AlertExplanationResponse:
    trace_id = f"trace-{uuid.uuid4().hex[:8]}"
    start_time = datetime.now()

    # Step 1: Guardrails on input
    try:
        sanitized_request = sanitize_input_request(request)
    except Exception as e:
        logger.error(f"Input sanitization failed: {e}")
        return generate_fallback_explanation(request, trace_id)

    # Step 2: Prepare prompt
    user_prompt = build_user_prompt(sanitized_request)

    # Step 3: Call LLM
    client = LLMClient()
    if not client.enabled or not client.api_key:
        logger.warning(f"LLM disabled or API key missing. Using fallback for alert {request.alert_id}")
        return generate_fallback_explanation(sanitized_request, trace_id)

    raw_response = None
    try:
        raw_response = client.generate(SYSTEM_PROMPT, user_prompt, is_json_response=True)
    except Exception as e:
        logger.error(f"LLM Provider error: {e}")
        return generate_fallback_explanation(sanitized_request, trace_id)

    # Step 4: Validate and parse output
    try:
        response = validate_llm_response(raw_response, sanitized_request)
    except Exception as e:
        logger.error(f"Output validation failed: {e}. Output was: {raw_response}")
        # One retry could be implemented here, but falling back for now
        return generate_fallback_explanation(sanitized_request, trace_id)

    # Step 5: Post-processing
    # Ensure deterministic confidence
    response.confidence = calculate_confidence(sanitized_request)
    
    # Metadata enforcement
    response.trace_id = trace_id
    response.generated_by = "llm"
    response.generated_at = datetime.now(timezone.utc)
    response.model_name = client.model
    response.prompt_version = client.provider  # Just a placeholder or from config
    response.evidence_hash = compute_evidence_hash(sanitized_request)
    
    latency_ms = (datetime.now() - start_time).total_seconds() * 1000
    logger.info(
        f"Generated LLM explanation for {request.alert_id}",
        extra={
            "trace_id": trace_id,
            "latency_ms": latency_ms,
            "generated_by": "llm",
            "model_name": client.model,
        }
    )

    return response
