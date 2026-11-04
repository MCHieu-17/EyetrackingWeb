"""Authenticated backend tools and deterministic Vietnamese presentation."""

import os
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import httpx

from app.settings import internal_token


class AccessRevoked(RuntimeError):
    pass


@lru_cache(maxsize=1)
def backend_client():
    return httpx.AsyncClient(
        base_url=os.getenv("CHATBOT_BACKEND_URL", "http://backend:8001"),
        headers={"X-Chatbot-Token": internal_token()},
        timeout=10,
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
    )


async def query(state, operation, target=""):
    response = await backend_client().post(
        "/internal/chat/lms-query",
        json={
            "session_id": state["thread_id"],
            "context_key": state.get("context_key", ""),
            "operation": operation,
            "target": target,
        },
    )
    if response.status_code in {401, 403, 404}:
        raise AccessRevoked("Quyền chat hoặc ngữ cảnh đã thay đổi. Vui lòng mở lại phiên chat.")
    response.raise_for_status()
    data = response.json()
    if str(data.get("course_id")) != str(state["course_id"]):
        raise AccessRevoked("Phiên chat không thuộc khóa học được yêu cầu.")
    return data


async def check_access(state):
    await query(state, "access")


def escape(text):
    import re

    return re.sub(r"([\\`*_{}\[\]()<>|#$])", r"\\\1", str(text)).replace("\n", " ")


def date(value):
    if not value:
        return "chưa đặt hạn nộp"
    return (
        datetime.fromisoformat(value)
        .astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
        .strftime("%d/%m/%Y %H:%M (GMT+7)")
    )


def render(data, operation):
    if data.get("clarification"):
        choices = "\n".join(
            f"- {escape(c['title'])} — `{c['id']}`" for c in data.get("choices", [])
        )
        return data["clarification"] + ("\n" + choices if choices else "")
    if "course" in data:
        c = data["course"]
        return f"[{escape(c['title'])}]({c['url']})\n\n{escape(c['description'])}"
    if "lessons" in data:
        return "| Chương | Bài học |\n|---|---|\n" + "\n".join(
            f"| {escape(x['module'])} | [{escape(x['title'])}]({x['url']}) |"
            if x["url"]
            else f"| {escape(x['module'])} | {escape(x['title'])} |"
            for x in data["lessons"]
        )
    rows = data.get("assignments", [])
    if not rows:
        return "Khóa học chưa có bài tập được công bố."
    header = "| Bài tập | Trạng thái | Thời lượng | Hạn nộp | Hạn lượt làm | Còn lại |" + (
        " Điểm |" if operation == "results" else ""
    )
    lines = [header, "|---|---|---|---|---|---|" + ("---|" if operation == "results" else "")]
    for x in rows:
        remaining = (
            "—"
            if x["remaining_seconds"] is None
            else f"{x['remaining_seconds'] // 60} phút {x['remaining_seconds'] % 60} giây"
        )
        line = f"| [{escape(x['title'])}]({x['url']}) | {x['status']} | {x['duration_minutes']} phút | {date(x['due_at'])} | {date(x['attempt_deadline'])} | {remaining} |"
        if operation == "results":
            line += (
                f" {x['score']}/{x['max_score']} |"
                if x["score"] is not None
                else " chưa có kết quả được xem |"
            )
        lines.append(line)
    if operation == "assignment" and rows[0].get("instructions"):
        lines.extend(["", escape(rows[0]["instructions"])])
    return "\n".join(lines)
