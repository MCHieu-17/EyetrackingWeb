from app.workflow.guardrails import (
    ClaimVerification,
    VerificationResult,
    _check_result,
    safe_response,
)

DOC = "Khóa chính (primary key) xác định duy nhất mỗi hàng trong bảng."
DRAFT = "Khóa chính xác định duy nhất mỗi hàng trong bảng [1]."


def _claim(**overrides):
    data = {
        "claim": "Khóa chính xác định duy nhất mỗi hàng trong bảng",
        "citation_ids": [1],
        "claim_type": "course",
        "supported": True,
        "evidence_quote": "Khóa chính (primary key) xác định duy nhất mỗi hàng",
        "reason": "",
        "violates_no_solution": False,
    }
    data.update(overrides)
    return ClaimVerification(**data)


def test_valid_course_claim():
    result = VerificationResult(claims=[_claim()])
    assert _check_result(result, DRAFT, [{"content": DOC}], "course_qa") == []


def test_course_claim_without_citation():
    result = VerificationResult(claims=[_claim(citation_ids=[])])
    problems = _check_result(result, DRAFT, [{"content": DOC}], "course_qa")
    assert any("thiếu citation" in problem for problem in problems)


def test_invalid_citation():
    result = VerificationResult(claims=[_claim(citation_ids=[2])])
    problems = _check_result(result, DRAFT, [{"content": DOC}], "course_qa")
    assert any("không tồn tại" in problem for problem in problems)


def test_evidence_quote_not_in_document():
    result = VerificationResult(
        claims=[_claim(evidence_quote="Khóa ngoại liên kết hai bảng")]
    )
    problems = _check_result(result, DRAFT, [{"content": DOC}], "course_qa")
    assert any("Evidence quote không khớp" in problem for problem in problems)


def test_general_claim_without_label():
    draft = "Đây là kiến thức chung."
    result = VerificationResult(
        claims=[
            _claim(
                claim="Đây là kiến thức chung",
                citation_ids=[],
                claim_type="general",
                supported=True,
                evidence_quote="",
            )
        ]
    )
    problems = _check_result(result, draft, [], "course_qa")
    assert any("thiếu label" in problem for problem in problems)


def test_general_claim_with_label():
    draft = "Ngoài tài liệu môn học: đây là kiến thức chung."
    result = VerificationResult(
        claims=[
            _claim(
                claim="đây là kiến thức chung",
                citation_ids=[],
                claim_type="general",
                supported=True,
                evidence_quote="",
            )
        ]
    )
    assert _check_result(result, draft, [], "course_qa") == []


def test_general_claim_with_citation_rejected():
    draft = "Ngoài tài liệu môn học: đây là kiến thức chung [1]."
    result = VerificationResult(
        claims=[
            _claim(
                claim="đây là kiến thức chung",
                citation_ids=[1],
                claim_type="general",
                supported=True,
                evidence_quote="",
            )
        ]
    )
    problems = _check_result(result, draft, [{"content": DOC}], "course_qa")
    assert any("không được cite" in problem for problem in problems)


def test_no_solution_violation_for_hints():
    result = VerificationResult(claims=[_claim(violates_no_solution=True)])
    problems = _check_result(result, DRAFT, [{"content": DOC}], "exercise_hints")
    assert any("Lộ đáp án" in problem for problem in problems)


def test_no_solution_allowed_for_review():
    result = VerificationResult(claims=[_claim(violates_no_solution=True)])
    assert _check_result(result, DRAFT, [{"content": DOC}], "exercise_review") == []


def test_verifier_missing_claims():
    draft = (
        "Đây là câu một đủ dài để đếm. "
        "Đây là câu hai đủ dài để đếm. "
        "Đây là câu ba đủ dài để đếm."
    )
    result = VerificationResult(claims=[])
    problems = _check_result(result, draft, [], "course_qa")
    assert any("không đủ để xác minh" in problem for problem in problems)


def test_safe_response_hints():
    assert "gợi ý" in safe_response("exercise_hints").lower()


def test_safe_response_course():
    assert "căn cứ" in safe_response("course_qa").lower()
