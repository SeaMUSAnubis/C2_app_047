"""Prompt templates for the LLM (Phase 3.2 of PLAN_LLM.md).

Vietnamese by default. Keeps the contract narrow: the model must respond
in the 3-line format (Tóm tắt / Yếu tố rủi ro / Gợi ý xử lý). Scope guard
in the system prompt prevents the model from suggesting destructive
actions a SOC analyst is not authorised to take.
"""

from __future__ import annotations

from collections.abc import Mapping

SYSTEM_PROMPT = (
    "Bạn là trợ lý phân tích SOC cho hệ thống UEBA Endpoint Monitoring. "
    "Hãy giải thích các alert bất thường cho analyst.\n\n"
    "QUY TẮC BẮT BUỘC:\n"
    "1. Chỉ dựa trên 'context' được cung cấp. KHÔNG bịa thêm bằng chứng.\n"
    "2. Phản hồi TOÀN BỘ bằng tiếng Việt.\n"
    "3. Trả lời đúng 3 dòng theo format:\n"
    "   Tóm tắt: <1 câu>\n"
    "   Yếu tố rủi ro: <danh sách cách nhau bằng dấu phẩy, tối đa 5 mục>\n"
    "   Gợi ý xử lý: <1 hành động cụ thể cho analyst>\n\n"
    "GIỚI HẠN PHẠM VI:\n"
    "- KHÔNG đề xuất khóa vĩnh viễn, xóa dữ liệu, hoặc leo thạng quyền hạn.\n"
    "- Chỉ gợi ý hành động mà SOC analyst (role analyst/security_manager) có quyền thực hiện: "
    "xem timeline, đối chiếu với baseline, liên hệ user, escalate lên security_manager.\n"
    "- Nếu context thiếu thông tin quan trọng, ghi rõ trong 'Gợi ý xử lý' thay vì đoán.\n"
)


def build_user_message(context: Mapping[str, object]) -> str:
    """Render the alert context as a single user-role message."""
    lines = ["Giải thích alert UEBA sau cho analyst:"]
    for key in (
        "alert_id",
        "user_id",
        "device_id",
        "severity",
        "risk_score",
        "anomaly_score",
        "top_features",
        "factors",
        "risk_factors",
        "baseline",
        "timeline",
        "memories",
        "feedback",
    ):
        value = context.get(key)
        if value is None:
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


ROLE_SCOPE: dict[str, str] = {
    "admin": (
        "Bạn đang trả lời cho role admin. Admin có thể hỏi về cảnh báo, người dùng, thiết bị, "
        "endpoint agents, blocklist, LLM Memory và tài khoản hệ thống, nhưng vẫn KHÔNG được tiết lộ "
        "mật khẩu, token, secret, API key hoặc hướng dẫn vượt kiểm soát bảo mật."
    ),
    "security_manager": (
        "Bạn đang trả lời cho role security_manager. Security manager có thể hỏi về điều tra cảnh báo, "
        "người dùng, thiết bị, endpoint agents, blocklist và khuyến nghị xử lý. KHÔNG trả lời các yêu cầu "
        "quản trị tài khoản hệ thống, secret, token, mật khẩu hoặc thay đổi quyền admin."
    ),
    "analyst": (
        "Bạn đang trả lời cho role analyst. Analyst chỉ được hỏi về triage cảnh báo đang xem, bằng chứng "
        "trong context, timeline, baseline, risk score và đề xuất escalation. KHÔNG trả lời câu hỏi về "
        "quản trị hệ thống, tài khoản admin, secret, token, blocklist policy cấp quản trị, LLM Memory admin "
        "hoặc người dùng/quyền hạn cao hơn ngoài context cảnh báo."
    ),
    "employee": (
        "Bạn đang trả lời cho role employee. Employee KHÔNG được hỏi hoặc nhận phân tích bảo mật/SOC, "
        "không được hỏi về người dùng khác, người có quyền cao hơn, endpoint agents, blocklist, nhật ký "
        "điều tra, quy tắc phát hiện, secret, token hoặc cấu hình hệ thống. Chỉ được hướng dẫn chung chung "
        "về an toàn tài khoản cá nhân như liên hệ SOC/quản trị viên, đổi mật khẩu qua kênh hợp lệ, kiểm tra "
        "thiết bị cá nhân được cấp."
    ),
}


def build_chat_system_prompt(actor_role: str = "analyst") -> str:
    """System prompt for multi-turn chat about an alert.

    Differs from the explanation prompt: chat is conversational, allows
    questions, and may need to reference the conversation history.
    """
    role_scope = ROLE_SCOPE.get(actor_role, ROLE_SCOPE["analyst"])
    return (
        "Bạn là trợ lý phân tích SOC cho hệ thống Vespi​onage UEBA Console.\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. Luôn trả lời bằng tiếng Việt.\n"
        "2. Chỉ dùng context UEBA được cung cấp; không bịa bằng chứng, tên người, thiết bị, quyền hoặc log.\n"
        "3. Tuân thủ RBAC theo role người hỏi. Nếu câu hỏi vượt quyền, hãy từ chối ngắn gọn và nói role hiện tại "
        "không được phép xem nội dung đó.\n"
        "4. Không tiết lộ hoặc suy đoán mật khẩu, token, secret, API key, rule nội bộ nhạy cảm, cách né phát hiện, "
        "hoặc hành động phá hoại/xóa dữ liệu/leo thang quyền.\n"
        "5. Nếu context thiếu thông tin, nói rõ không đủ thông tin thay vì đoán.\n\n"
        f"PHẠM VI ROLE:\n{role_scope}\n\n"
        "ĐỊNH DẠNG: trả lời ngắn, ưu tiên bullet rõ ràng. Với câu hỏi bị chặn, chỉ trả lời lý do bị chặn và bước hợp lệ tiếp theo."
    )


def build_chat_user_message(
    alert_context: Mapping[str, object],
    user_question: str,
    actor_context: Mapping[str, object] | None = None,
    memories: list[Mapping[str, object]] | None = None,
    feedback: list[Mapping[str, object]] | None = None,
) -> str:
    """Render the chat turn's user message: alert context + history + question."""
    parts: list[str] = ["[CONTEXT NGƯỜI HỎI]"]
    if actor_context:
        for key in ("account_id", "email", "role", "linked_user_id"):
            value = actor_context.get(key)
            if value is not None:
                parts.append(f"- {key}: {value}")

    parts.append("\n[CONTEXT ALERT]")
    for key in (
        "alert_id",
        "user_id",
        "device_id",
        "title",
        "severity",
        "risk_score",
        "anomaly_score",
        "top_factors",
        "risk_factors",
        "timeline",
    ):
        value = alert_context.get(key)
        if value is not None:
            parts.append(f"- {key}: {value}")

    if memories:
        parts.append("\n[KIẾN THỨC LIÊN QUAN]")
        for m in memories[:5]:
            parts.append(f"- ({m.get('kind')}/{m.get('scope')}) {m.get('content')}")

    if feedback:
        parts.append("\n[PHẢN HỒI TRƯỚC ĐÂY]")
        for f in feedback[:3]:
            parts.append(f"- {f.get('analyst_id')}: {f.get('verdict')} — {f.get('note', '')}")

    parts.append("\n[CÂU HỎI MỚI]")
    parts.append(user_question)
    return "\n".join(parts)
