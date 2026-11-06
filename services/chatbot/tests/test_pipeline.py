from app.workflow import pipeline


def _state():
    return {}

def test_retrieval_resolves_first_middle_last_quiz_question_without_answer_key():
    state = {
        "question": "Gợi ý câu cuối",
        "assignment_context": "\n".join(
            f"Câu {n}: TOPIC-{n}\n- a: OPTION-{n}\nĐáp án đúng: SECRET" for n in range(1, 11)
        ),
    }
    assert "TOPIC-10" in pipeline.retrieval_query(state)
    assert "TOPIC-1\n" not in pipeline.retrieval_query(state)
    assert "SECRET" not in pipeline.retrieval_query(state)
    state["question"] = "Chữa câu 5"
    assert "TOPIC-5" in pipeline.retrieval_query(state)
    assert "TOPIC-10" not in pipeline.retrieval_query(state)
    state["question"] = "câu đầu và câu giữa"
    assert "TOPIC-1" in pipeline.retrieval_query(state) and "TOPIC-5" in pipeline.retrieval_query(
        state
    )


def test_question_overview_preserves_uncertainty_and_never_paraphrases_an_answer(monkeypatch):
    state = _state() | {
        "question": "Đề có bao nhiêu câu? Kể chủ đề câu đầu, câu giữa và câu cuối.",
        "assignment_context": "\n".join(
            f"Câu {n}: Khóa có thể gồm nhiều cột không?\nĐáp án đúng: SECRET" for n in range(1, 11)
        ),
    }


    answer = pipeline.assignment_overview(state)
    citations, verified = [], True
    assert "Đề có 10 câu hỏi" in answer
    for n in (1, 5, 10):
        assert f"Câu {n}: Khóa có thể gồm nhiều cột không?" in answer
    assert "SECRET" not in answer and citations == [] and verified is True
