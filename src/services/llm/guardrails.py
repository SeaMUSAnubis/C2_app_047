import re

from pydantic import ValidationError

from src.models.explanation import AlertExplanationRequest, AlertExplanationResponse

# Simple regexes to match potential secrets
SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]+"), "Bearer [REDACTED]"),
    (re.compile(r"api[_\-]?key\s*[:=]\s*[a-zA-Z0-9_\-\.]+"), "api_key=[REDACTED]"),
    (re.compile(r"password\s*[:=]\s*[\S]+"), "password=[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_input_request(request: AlertExplanationRequest) -> AlertExplanationRequest:
    # Truncate and redact long text
    for event in request.timeline_events:
        if event.description:
            event.description = redact_secrets(event.description[:1000])
        if event.source_file:
            event.source_file = redact_secrets(event.source_file[:500])

    for url_obj in request.suspicious_urls:
        url_obj.url = redact_secrets(url_obj.url[:1000])
        if url_obj.reason:
            url_obj.reason = redact_secrets(url_obj.reason[:500])

    if request.main_reason:
        request.main_reason = redact_secrets(request.main_reason[:1000])

    return request


def validate_llm_response(raw_json: str, request: AlertExplanationRequest) -> AlertExplanationResponse:
    try:
        response = AlertExplanationResponse.model_validate_json(raw_json)
    except ValidationError as e:
        raise ValueError(f"LLM output failed schema validation: {e}") from e

    # Check that alert metadata was preserved
    if response.alert_id != request.alert_id:
        raise ValueError("LLM changed the alert_id")
    if response.risk_score != request.risk_score:
        raise ValueError("LLM changed the risk_score")
    if response.severity != request.severity:
        raise ValueError("LLM changed the severity")

    # Check for hallucinated domains
    input_domains = set()
    for u in request.suspicious_urls:
        if u.domain:
            input_domains.add(u.domain)
        # Also try to parse domain from url if domain is empty
        # A simple check: if domain is hallucinated, it wasn't in input
        
    for domain in response.suspicious_domains:
        if domain not in input_domains and not any(domain in u.url for u in request.suspicious_urls):
            # It might be hallucinated, but we can just drop it or raise an error
            # For strict guardrails, we raise error
            # raise ValueError(f"Hallucinated domain detected: {domain}")
            # But the prompt says "Validator phải reject hoặc loại bỏ domain đó."
            pass
            
    # Filter out hallucinated domains
    response.suspicious_domains = [
        d for d in response.suspicious_domains
        if d in input_domains or any(d in u.url for u in request.suspicious_urls)
    ]

    return response
