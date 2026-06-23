from datetime import datetime, timezone
import uuid

from src.config import settings
from src.models.explanation import (
    AlertExplanationRequest,
    AlertExplanationResponse,
    ExplanationEvidence,
    RecommendedAction,
)


def generate_fallback_explanation(request: AlertExplanationRequest, trace_id: str) -> AlertExplanationResponse:
    summary = f"Cảnh báo {request.alert_id} có mức độ {request.severity} và điểm rủi ro {request.risk_score}."
    
    why_suspicious = []
    if request.main_reason:
        why_suspicious.append(request.main_reason)
    
    evidence = []
    evidence.append(ExplanationEvidence(
        evidence_type="risk_score",
        description=f"Điểm rủi ro (Risk score) được hệ thống đánh giá là {request.risk_score}/100.",
        source_reference=request.alert_id
    ))
    
    for feature in request.anomalous_features[:3]:
        evidence.append(ExplanationEvidence(
            evidence_type="anomalous_feature",
            description=f"Tính năng bất thường: {feature.feature_name} (Giá trị: {feature.feature_value})",
            source_reference=feature.feature_name
        ))
        why_suspicious.append(f"Giá trị bất thường tại {feature.feature_name}.")

    baseline_text = None
    if request.baseline_comparisons:
        baseline_text = "Hoạt động ghi nhận có sự sai lệch so với dữ liệu baseline cơ sở."
        for comp in request.baseline_comparisons[:3]:
            evidence.append(ExplanationEvidence(
                evidence_type="baseline_deviation",
                description=f"Sai lệch baseline tại {comp.feature_name}: {comp.current_value} so với {comp.baseline_value}.",
                source_reference=comp.feature_name
            ))
    else:
        baseline_text = "Không có dữ liệu so sánh baseline cho cảnh báo này."
        
    for event in request.timeline_events:
        if event.risk_marker:
            evidence.append(ExplanationEvidence(
                evidence_type="timeline_event",
                description=f"Sự kiện đáng chú ý: {event.description}",
                source_reference=event.event_id
            ))
            
    suspicious_domains = []
    for url in request.suspicious_urls:
        evidence.append(ExplanationEvidence(
            evidence_type="suspicious_url",
            description=f"URL đáng ngờ: {url.url}",
            source_reference=url.domain or url.url
        ))
        if url.domain:
            suspicious_domains.append(url.domain)

    if not why_suspicious:
        why_suspicious.append("Có các hoạt động bất thường được phát hiện bởi mô hình anomaly detection.")

    recommended_actions = [
        RecommendedAction(
            action="Kiểm tra lại toàn bộ chuỗi sự kiện và xác minh hành vi của người dùng.",
            priority="high",
            requires_human_approval=True
        )
    ]
    
    return AlertExplanationResponse(
        alert_id=request.alert_id,
        summary=summary,
        why_suspicious=why_suspicious,
        evidence=evidence,
        baseline_comparison=baseline_text,
        recommended_actions=recommended_actions,
        suspicious_domains=suspicious_domains,
        confidence=0.3,  # Rule-based is inherently lower confidence in explanation quality
        limitations=[
            "Hệ thống giải thích AI đang không khả dụng (timeout, lỗi, hoặc bị tắt).",
            "Giải thích này được tạo bằng quy tắc cơ sở (rule-based fallback).",
            "Vui lòng xem xét các sự kiện gốc để đánh giá thêm."
        ],
        generated_by="rule_based",
        model_name=settings.llm_model,
        prompt_version=settings.llm_prompt_version,
        risk_score=request.risk_score,
        severity=request.severity,
        safety_flags=[],
        generated_at=datetime.now(timezone.utc),
        trace_id=trace_id
    )
