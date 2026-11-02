"""Kiểm duyệt đầu ra: citation đúng tài liệu + không lộ đáp án.

Hai lớp:
1. LLM verifier: trả về từng claim, citation_ids, claim_type, supported,
   evidence_quote, violates_no_solution.
2. Code checks (không tin LLM):
   - claim phải thật sự có trong answer;
   - course claim phải có citation hợp lệ;
   - evidence_quote phải khớp nội dung tài liệu được cite;
   - general claim chỉ được phép khi có label hoặc intent study_skills;
   - exercise_hints không được lộ đáp án/lời giải.

Fail-closed: verifier lỗi -> coi như không đạt; pipeline retry rồi trả câu an
toàn, không bao giờ trả bản nháp chưa kiểm duyệt.
"""

import logging
import re
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.workflow.citations import claim_in_answer, quote_supported
from app.workflow.prompts import VERIFIER_SYSTEM_PROMPT
from app.workflow.providers import get_llm
from app.workflow.retrieval import format_context
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)

GENERAL_LABEL = "Ngoài tài liệu môn học"


class ClaimVerification(BaseModel):
    claim: str = Field(description="Một ý trong draft answer.")
    citation_ids: list[int] = Field(default_factory=list)
    claim_type: Literal["course", "general", "not_found", "meta"]
    supported: bool = False
    evidence_quote: str = ""
    reason: str = ""
    violates_no_solution: bool = False


class VerificationResult(BaseModel):
    claims: list[ClaimVerification] = Field(default_factory=list)
    feedback: str = ""


_verifier_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", VERIFIER_SYSTEM_PROMPT),
        (
            "human",
            "Intent: {intent}\n\n"
            "Câu hỏi của sinh viên:\n{question}\n\n"
            "Draft answer:\n{draft}\n\n"
            "Tài liệu tham khảo:\n{context}",
        ),
    ]
)


def _verifier_chain():
    return _verifier_prompt | get_llm(purpose="verify").with_structured_output(
        VerificationResult
    )


def _sentence_count(text: str) -> int:
    parts = re.split(r"[.!?。！？]\s+", text or "")
    return len([part for part in parts if len(part.strip()) > 10])


def _check_result(
    result: VerificationResult,
    draft: str,
    docs: list[dict],
    intent: str,
) -> list[str]:
    problems: list[str] = []

    # Verifier bỏ sót quá nhiều claim -> không đủ tin cậy.
    sentences = _sentence_count(draft)
    if sentences >= 3 and len(result.claims) < max(1, sentences // 2):
        problems.append(
            f"Verifier chỉ trả {len(result.claims)} claim cho {sentences} câu; "
            "không đủ để xác minh toàn bộ câu trả lời."
        )

    for claim in result.claims:
        label = claim.claim[:100]

        if not claim_in_answer(claim.claim, draft):
            problems.append(f"Claim không có trong answer: {label}")
            continue

        if claim.claim_type == "course":
            if not claim.citation_ids:
                problems.append(f"Course claim thiếu citation: {label}")
                continue
            for cid in claim.citation_ids:
                if cid < 1 or cid > len(docs):
                    problems.append(f"Citation [{cid}] không tồn tại: {label}")
                    continue
                if not claim.supported:
                    problems.append(f"Claim không được tài liệu [{cid}] hỗ trợ: {label}")
                    continue
                if not claim.evidence_quote.strip():
                    problems.append(f"Thiếu evidence quote cho citation [{cid}]: {label}")
                    continue
                document = docs[cid - 1].get("content") or ""
                if not quote_supported(claim.evidence_quote, document):
                    problems.append(
                        f"Evidence quote không khớp tài liệu [{cid}]: {label}"
                    )

        elif claim.claim_type == "general":
            if intent != "study_skills" and GENERAL_LABEL not in draft:
                problems.append(f"General claim thiếu label '{GENERAL_LABEL}': {label}")
            if claim.citation_ids:
                problems.append(f"General claim không được cite tài liệu môn: {label}")

        elif claim.claim_type == "not_found":
            # Được phép: câu trả lời nói tài liệu không chứa thông tin.
            pass

        elif claim.claim_type == "meta":
            # Được phép: câu về format/hướng dẫn tiếp theo.
            pass

        if intent == "exercise_hints" and claim.violates_no_solution:
            problems.append(f"Lộ đáp án/lời giải: {label}")

    return problems


def verify_answer(state: ChatState, draft: str) -> dict:
    """Chấm draft; trả dict {ok, feedback, claims, no_solution_ok}."""
    docs = state.get("retrieved_docs") or []
    intent = state.get("intent") or "course_qa"

    try:
        result: VerificationResult = _verifier_chain().invoke(
            {
                "intent": intent,
                "question": state["question"],
                "draft": draft,
                "context": format_context(docs) or "(không có tài liệu)",
            }
        )
    except Exception:
        logger.warning("Verifier lỗi — coi như không đạt", exc_info=True)
        return {
            "ok": False,
            "feedback": "Không kiểm tra được citation; hãy viết lại chặt chẽ hơn.",
            "claims": [],
            "no_solution_ok": False,
        }

    problems = _check_result(result, draft, docs, intent)
    no_solution_ok = not any(
        claim.violates_no_solution for claim in result.claims
    )
    feedback = "\n".join(problems) or result.feedback
    return {
        "ok": not problems,
        "feedback": feedback,
        "claims": [claim.model_dump() for claim in result.claims],
        "no_solution_ok": no_solution_ok,
    }


def safe_response(intent: str) -> str:
    """Câu trả lời an toàn khi không verify được sau số lần tối đa."""
    if intent == "exercise_hints":
        return (
            "Mình chưa thể đưa ra gợi ý chắc chắn mà không lộ đáp án cho câu hỏi "
            "này. Bạn hãy trình bày hướng làm hiện tại hoặc phần kiến thức còn "
            "vướng mắc, mình sẽ gợi ý từng bước để bạn tự tìm ra lời giải."
        )
    if intent == "exercise_review":
        return (
            "Mình chưa tìm được căn cứ chính xác trong tài liệu môn học để chữa "
            "bài này. Bạn thử xem lại slide liên quan hoặc hỏi giảng viên để "
            "đối chiếu đáp án nhé."
        )
    return (
        "Mình chưa tìm được căn cứ chính xác trong tài liệu môn học cho câu hỏi "
        "này. Bạn thử hỏi cụ thể hơn hoặc xem lại slide liên quan nhé."
    )
