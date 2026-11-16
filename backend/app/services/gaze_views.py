"""Tiện ích đóng các lượt xem nội dung (content_views) còn mở.

Lượt xem được đóng khi học viên chuyển slide, kết thúc phiên học, kết thúc ca
học hoặc maintenance dọn phiên hết hạn. Hàm ở đây chỉ cập nhật ``ended_at``;
gaze thô và metrics dẫn xuất không bị ảnh hưởng.
"""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gaze import ContentView, LearningSession


async def close_open_views(
    db: AsyncSession, session_ids: Iterable[str], ended_at: datetime
) -> int:
    """Đóng mọi content_view đang mở của các phiên học; trả số row đã sửa.

    ``ended_at`` không được nhỏ hơn ``started_at`` của từng row (dùng
    ``greatest`` để xử lý khi client gửi enteredAt sớm hơn dự kiến).
    """
    ids = list(session_ids)
    if not ids:
        return 0
    result = await db.execute(
        update(ContentView)
        .where(
            ContentView.session_id.in_(ids),
            ContentView.ended_at.is_(None),
        )
        .values(ended_at=func.greatest(ContentView.started_at, ended_at))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount or 0


async def close_open_views_for_visit(
    db: AsyncSession, visit_id: str, ended_at: datetime
) -> int:
    """Đóng content_view đang mở của toàn bộ phiên học thuộc một ca học."""
    session_ids = list(
        (
            await db.execute(
                select(LearningSession.id).where(
                    LearningSession.course_visit_id == visit_id
                )
            )
        ).scalars()
    )
    return await close_open_views(db, session_ids, ended_at)
