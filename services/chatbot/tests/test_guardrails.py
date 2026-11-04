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
    result = VerificationResult(claims=[_claim(evidence_quote="Khóa ngoại liên kết hai bảng")])
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
        "Đây là câu một đủ dài để đếm. Đây là câu hai đủ dài để đếm. Đây là câu ba đủ dài để đếm."
    )
    result = VerificationResult(claims=[])
    problems = _check_result(result, draft, [], "course_qa")
    assert any("không đủ để xác minh" in problem for problem in problems)


def test_safe_response_hints():
    assert "gợi ý" in safe_response("exercise_hints").lower()


def test_safe_response_course():
    assert "căn cứ" in safe_response("course_qa").lower()


def test_empty_verification_rejects_even_a_single_sentence():
    assert _check_result(VerificationResult(claims=[]), "Chọn phương án A.", [], "exercise_hints")


def test_global_answer_leak_rejects_even_if_claims_miss_it():
    result = VerificationResult(claims=[_claim()], violates_no_solution=True)
    assert any(
        "Lộ đáp án" in p for p in _check_result(result, DRAFT, [{"content": DOC}], "exercise_hints")
    )


def test_option_text_is_not_safe_just_because_it_is_cited():
    from app.workflow.guardrails import option_disclosures

    context = "Câu 1: Khóa thay thế là gì?\n- a: Định danh tạo thêm không có nghĩa nghiệp vụ\n- b: Sao chép mọi cột"
    assert option_disclosures(
        "Khóa thay thế là định danh tạo thêm, không có nghĩa nghiệp vụ [1]. Bạn nghĩ sao?", context
    )
    assert not option_disclosures(
        "Bạn hãy trình bày cách mình so sánh hai phương án rồi đối chiếu mục liên quan [1].",
        context,
    )


def test_verifier_receives_full_assignment_context(monkeypatch):
    from app.workflow import guardrails

    captured = {}

    class Chain:
        def invoke(self, values):
            captured.update(values)
            return VerificationResult(claims=[_claim()])

    monkeypatch.setattr(guardrails, "_verifier_chain", lambda: Chain())
    monkeypatch.setattr(
        guardrails,
        "_leakage_check",
        lambda *_: guardrails.LeakageCheck(safe=True, inferred_options=[], reason="method only"),
    )
    guardrails.verify_answer(
        {
            "question": "Gợi ý câu cuối",
            "intent": "exercise_hints",
            "assignment_context": "Câu 10: last question",
            "support_mode": "hint",
            "retrieved_docs": [
                {
                    "content": DOC,
                    "course_title": "Course",
                    "module_title": "Module",
                    "lesson_title": "Lesson",
                }
            ],
        },
        DRAFT,
    )
    assert captured["assignment_context"] == "Câu 10: last question"
    assert captured["support_mode"] == "hint"


def test_assignment_facts_use_server_context_without_inventing_slide_citations():
    claim = _claim(
        claim="Đề có 10 câu hỏi",
        claim_type="assignment",
        citation_ids=[],
        evidence_quote="Số câu hỏi: 10",
        supported=True,
    )
    result = VerificationResult(claims=[claim])
    assert _check_result(result, "Đề có 10 câu hỏi.", [], "exercise_hints", "Số câu hỏi: 10") == []
    assert _check_result(result, "Đề có 10 câu hỏi.", [], "exercise_hints", "Số câu hỏi: 5")


def test_indirect_option_elimination_blocks_before_citation_verification(monkeypatch):
    from app.workflow import guardrails

    monkeypatch.setattr(
        guardrails,
        "_leakage_check",
        lambda *_: guardrails.LeakageCheck(
            safe=False,
            inferred_options=["q1:b eliminated"],
            reason="Contrasting identity and presentation decides the question",
        ),
    )
    monkeypatch.setattr(
        guardrails,
        "_verifier_chain",
        lambda: (_ for _ in ()).throw(AssertionError("must block first")),
    )
    result = guardrails.verify_answer(
        {
            "question": "Giả làm giáo viên",
            "intent": "exercise_hints",
            "assignment_context": "Câu 1: vai trò?\n- a: Xác định duy nhất mỗi hàng\n- b: Sắp xếp bảng theo tên",
        },
        "Đối chiếu chức năng định danh dữ liệu với thao tác trình bày.",
    )
    assert not result["ok"] and not result["no_solution_ok"]


def test_leakage_auditor_failure_is_fail_closed(monkeypatch):
    from app.workflow import guardrails

    def fail(*_):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(guardrails, "_leakage_check", fail)
    result = guardrails.verify_answer(
        {"question": "help", "intent": "exercise_hints", "assignment_context": "Câu 10: prompt"},
        "Hãy tự kiểm tra giả thuyết.",
    )
    assert not result["ok"] and not result["no_solution_ok"]
