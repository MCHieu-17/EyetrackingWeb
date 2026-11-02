"""Sinh câu trả lời theo intent, có citation rule và retry feedback."""

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.workflow.prompts import (
    CITATION_RULE,
    COURSE_QA_SYSTEM_PROMPT,
    EXERCISE_HINTS_SYSTEM_PROMPT,
    EXERCISE_REVIEW_SYSTEM_PROMPT,
    GENERAL_LABEL_RULE,
    OUT_OF_SCOPE_SYSTEM_PROMPT,
    STRICT_SUFFIX,
    STUDY_SKILLS_SYSTEM_PROMPT,
)
from app.workflow.providers import get_llm, message_text
from app.workflow.retrieval import format_context
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "course_qa": COURSE_QA_SYSTEM_PROMPT,
    "exercise_hints": EXERCISE_HINTS_SYSTEM_PROMPT,
    "exercise_review": EXERCISE_REVIEW_SYSTEM_PROMPT,
    "study_skills": STUDY_SKILLS_SYSTEM_PROMPT,
    "out_of_scope": OUT_OF_SCOPE_SYSTEM_PROMPT,
}

RETRIEVAL_INTENTS = {"course_qa", "exercise_hints", "exercise_review"}

_ANSWER_HUMAN = (
    "Vị trí hiện tại của sinh viên: {location}\n"
    "Bài tập đang mở: {assignment_title}\n\n"
    "Câu hỏi của sinh viên: {question}\n\n"
    "Ngữ cảnh bài tập:\n{assignment_context}\n\n"
    "Tài liệu tham khảo:\n{context}"
)

_answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "{system}"),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", _ANSWER_HUMAN),
    ]
)


def _history_messages(history: list[dict]) -> list:
    messages = []
    for item in history[-10:]:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if item.get("role") == "student":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages


def _location_label(state: ChatState) -> str:
    parts = [state.get("module_title"), state.get("lesson_title")]
    return " > ".join(part for part in parts if part) or "chưa xác định"


def answer(state: ChatState) -> str:
    """Sinh draft answer; retry sẽ kèm feedback từ verifier."""
    intent = state.get("intent") or "course_qa"
    system = SYSTEM_PROMPTS.get(intent, COURSE_QA_SYSTEM_PROMPT)

    if intent in RETRIEVAL_INTENTS:
        system = f"{system}\n{CITATION_RULE}\n{GENERAL_LABEL_RULE}"

    if state.get("attempts", 0) > 0:
        system = f"{system}\n{STRICT_SUFFIX}"
        feedback = (state.get("verification_feedback") or "").strip()
        if feedback:
            system = f"{system}\nVerifier feedback:\n{feedback}"

    chain = _answer_prompt | get_llm(purpose="answer")
    response = chain.invoke(
        {
            "system": system,
            "chat_history": _history_messages(state.get("history") or []),
            "location": _location_label(state),
            "assignment_title": state.get("assignment_title")
            or "không có (hỏi ngoài bài tập)",
            "assignment_context": state.get("assignment_context") or "không có",
            "question": state["question"],
            "context": format_context(state.get("retrieved_docs") or []),
        }
    )
    return message_text(response.content)
