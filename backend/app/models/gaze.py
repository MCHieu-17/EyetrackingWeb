from datetime import datetime, timezone

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE")
    )
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    calibration_param_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_params.id")
    )
    status: Mapped[str] = mapped_column(String(20), server_default=text("'in_progress'"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tracking_consent: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # Viewport lúc tạo phiên và viewport lúc calibration. Hai bộ phải bằng nhau
    # (xem CHECK ở gaze_raw_samples + validate ở route).
    viewport_width_px: Mapped[int | None] = mapped_column(Integer)
    viewport_height_px: Mapped[int | None] = mapped_column(Integer)
    calibration_width_px: Mapped[int | None] = mapped_column(Integer)
    calibration_height_px: Mapped[int | None] = mapped_column(Integer)
    device_pixel_ratio: Mapped[float | None] = mapped_column(REAL)


class GazeEvent(Base):
    __tablename__ = "gaze_events"
    __table_args__ = (
        CheckConstraint("gaze_x >= 0 AND gaze_x <= 1", name="gaze_events_gaze_x_check"),
        CheckConstraint("gaze_y >= 0 AND gaze_y <= 1", name="gaze_events_gaze_y_check"),
        {"postgresql_partition_by": "RANGE (event_time)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    learning_session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = bài tập trắc nghiệm (không có slide). Toạ độ khi đó theo viewport.
    lesson_content_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesson_contents.id"), nullable=True
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=text("now()")
    )
    gaze_x: Mapped[float] = mapped_column(REAL, nullable=False)
    gaze_y: Mapped[float] = mapped_column(REAL, nullable=False)
    # Khung toạ độ của gaze_x/gaze_y: 'slide' (theo ảnh slide) | 'quiz' (theo viewport).
    surface: Mapped[str] = mapped_column(String(8), server_default=text("'slide'"))


class GazeSessionStat(Base):
    """Tổng hợp gaze mức PHIÊN cho bài KHÔNG có slide (bài tập trắc nghiệm).

    `gaze_slide_stats` không dùng được cho bài tập (gắn chặt lesson_content_id),
    nên tổng số sample / số sample trong màn hình / thời lượng xem của phiên bài
    tập lưu ở đây. Một dòng cho mỗi phiên học.
    """

    __tablename__ = "gaze_session_stats"

    learning_session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    total_samples: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    on_screen_samples: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    view_ms: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class GazeSlideStat(Base):
    __tablename__ = "gaze_slide_stats"
    __table_args__ = (
        UniqueConstraint("learning_session_id", "lesson_content_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    learning_session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE")
    )
    lesson_content_id: Mapped[str] = mapped_column(
        ForeignKey("lesson_contents.id", ondelete="CASCADE")
    )
    total_samples: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    on_slide_samples: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    view_ms: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class GazeRawSample(Base):
    """Một mẫu gaze RAW theo viewport (đã qua One-Euro smoothing ở AI service).

    Khác `gaze_events`:
      - Toạ độ chuẩn hoá theo VIEWPORT, không phải ảnh slide.
      - Cho phép gaze_x/gaze_y < 0 hoặc > 1 khi nhìn ra ngoài màn hình.
      - Lưu cả viewport lúc lấy mẫu và viewport lúc calibration; hai bộ phải
        bằng nhau (CHECK ở DB + validate ở route).
      - `status='no_face'` dùng gaze_x/gaze_y = NULL, không dùng sentinel (-1,-1).

    Partition theo tháng; không xoá partition cũ.
    """

    __tablename__ = "gaze_raw_samples"
    __table_args__ = (
        CheckConstraint(
            "viewport_width_px = calibration_width_px",
            name="gaze_raw_samples_viewport_width_check",
        ),
        CheckConstraint(
            "viewport_height_px = calibration_height_px",
            name="gaze_raw_samples_viewport_height_check",
        ),
        CheckConstraint(
            "(status = 'ok' AND gaze_x IS NOT NULL AND gaze_y IS NOT NULL) "
            "OR (status <> 'ok' AND gaze_x IS NULL AND gaze_y IS NULL)",
            name="gaze_raw_samples_status_coords_check",
        ),
        CheckConstraint(
            "gaze_x IS NULL OR (gaze_x > -100 AND gaze_x < 100)",
            name="gaze_raw_samples_gaze_x_check",
        ),
        CheckConstraint(
            "gaze_y IS NULL OR (gaze_y > -100 AND gaze_y < 100)",
            name="gaze_raw_samples_gaze_y_check",
        ),
        {"postgresql_partition_by": "RANGE (event_time)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    learning_session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    lesson_content_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesson_contents.id", ondelete="SET NULL"), nullable=True
    )
    layout_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("aoi_layout_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    client_ts_ms: Mapped[int | None] = mapped_column(BigInteger)
    gaze_x: Mapped[float | None] = mapped_column(REAL)
    gaze_y: Mapped[float | None] = mapped_column(REAL)
    slide_x: Mapped[float | None] = mapped_column(REAL)
    slide_y: Mapped[float | None] = mapped_column(REAL)
    status: Mapped[str] = mapped_column(String(16), server_default=text("'ok'"))
    surface: Mapped[str] = mapped_column(String(16), server_default=text("'lesson'"))
    viewport_width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    viewport_height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    calibration_width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    calibration_height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    device_pixel_ratio: Mapped[float] = mapped_column(REAL, nullable=False)
    layout_key: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16), server_default=text("'real'"))
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
