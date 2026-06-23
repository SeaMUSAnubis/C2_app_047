"""Pydantic schemas for LLM outputs (Phase 3.2 of PLAN_LLM.md).

Used to validate and normalise the structured response from the chat model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Explanation(BaseModel):
    """The 3-line Vietnamese explanation we surface to analysts.

    The model is asked to produce these three fields in order:
      - summary (1 sentence)
      - risk_factors (≤ 5 short tags, comma-separated by LLM)
      - recommended_action (1 sentence)
    """

    summary: str = Field(..., min_length=1, max_length=1000)
    risk_factors: list[str] = Field(default_factory=list, max_length=5)
    recommended_action: str = Field(..., min_length=1, max_length=1000)
    language: str = Field(default="vi", pattern=r"^(vi|en)$")
    model: str | None = None


def parse_explanation(text: str, *, model: str | None = None) -> Explanation | None:
    """Parse the LLM's freeform response into an `Explanation`.

    Tolerant parser:
      - Looks for lines starting with the 3 expected labels
        (`Tóm tắt:`, `Yếu tố rủi ro:`, `Gợi ý xử lý:`).
      - If any label is missing, returns None (caller falls back).
    """
    if not text:
        return None
    labels = {
        "summary": "Tóm tắt:",
        "risk_factors": "Yếu tố rủi ro:",
        "recommended_action": "Gợi ý xử lý:",
    }
    found: dict[str, str] = {}
    for line in text.splitlines():
        line_stripped = line.strip()
        for key, prefix in labels.items():
            if key in found:
                continue
            if line_stripped.startswith(prefix):
                value = line_stripped[len(prefix):].strip()
                if value:
                    found[key] = value
                break
    if not all(k in found for k in labels):
        return None
    risk_factors = [f.strip() for f in found["risk_factors"].split(",") if f.strip()]
    try:
        return Explanation(
            summary=found["summary"],
            risk_factors=risk_factors,
            recommended_action=found["recommended_action"],
            model=model,
        )
    except Exception:
        return None
