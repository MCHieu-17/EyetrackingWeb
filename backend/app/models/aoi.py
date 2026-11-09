from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import SlideVersion
    from app.models.gaze import (
        ContentPresentation,
        GazeBatch,
        GazeSample,
        LearningSession,
    )


class AoiSet(Base):
    __tablename__ = "aoi_sets"
    __table_args__ = (
        CheckConstraint("scope IN ('slide', 'ui')", name="aoi_sets_scope_check"),
        CheckConstraint(
            "state IN ('draft', 'published', 'archived')",
            name="aoi_sets_state_check",
        ),
        CheckConstraint("revision > 0", name="aoi_sets_revision_check"),
        CheckConstraint(
            "(scope = 'slide') = (slide_version_id IS NOT NULL)",
            name="aoi_sets_slide_scope_check",
        ),
        CheckConstraint(
            "(scope = 'ui') = (ui_schema_version IS NOT NULL)",
            name="aoi_sets_ui_scope_check",
        ),
        Index(
            "ux_aoi_sets_slide_revision",
            "slide_version_id",
            "revision",
            unique=True,
            postgresql_where=text("slide_version_id IS NOT NULL"),
        ),
        Index(
            "ux_aoi_sets_ui_revision",
            "ui_schema_version",
            "revision",
            unique=True,
            postgresql_where=text("ui_schema_version IS NOT NULL"),
        ),
        Index(
            "ux_aoi_sets_one_published_slide",
            "slide_version_id",
            unique=True,
            postgresql_where=text(
                "state = 'published' AND slide_version_id IS NOT NULL"
            ),
        ),
        Index(
            "ux_aoi_sets_one_published_ui",
            "ui_schema_version",
            unique=True,
            postgresql_where=text(
                "state = 'published' AND ui_schema_version IS NOT NULL"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    slide_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("slide_versions.id", ondelete="CASCADE")
    )
    ui_schema_version: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'draft'")
    )
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    slide_version: Mapped["SlideVersion | None"] = relationship()
    definitions: Mapped[list["AoiDefinition"]] = relationship(
        back_populates="aoi_set",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AoiDefinition(Base):
    __tablename__ = "aoi_definitions"
    __table_args__ = (
        UniqueConstraint("aoi_set_id", "code"),
        Index("idx_aoi_definitions_set", "aoi_set_id"),
        Index("idx_aoi_definitions_parent", "parent_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    aoi_set_id: Mapped[str] = mapped_column(
        ForeignKey("aoi_sets.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("aoi_definitions.id", ondelete="SET NULL")
    )
    geometry: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_container: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'custom'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    aoi_set: Mapped["AoiSet"] = relationship(back_populates="definitions")
    parent: Mapped["AoiDefinition | None"] = relationship(remote_side=[id])


class AoiLayoutSnapshot(Base):
    __tablename__ = "aoi_layout_snapshots"
    __table_args__ = (
        UniqueConstraint("presentation_id", "layout_generation"),
        CheckConstraint(
            "sequence_no >= 0", name="aoi_layout_snapshots_sequence_check"
        ),
        CheckConstraint(
            "layout_generation >= 0",
            name="aoi_layout_snapshots_generation_check",
        ),
        Index(
            "idx_aoi_layout_snapshots_presentation",
            "presentation_id",
            "captured_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    presentation_id: Mapped[str] = mapped_column(
        ForeignKey("content_presentations.id", ondelete="CASCADE"), nullable=False
    )
    ui_aoi_set_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey(
            "aoi_sets.id",
            name="aoi_layout_snapshots_ui_set_fkey",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    sequence_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    layout_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    image_transform: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    presentation: Mapped["ContentPresentation"] = relationship()
    ui_aoi_set: Mapped["AoiSet | None"] = relationship()
    rects: Mapped[list["AoiLayoutRect"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", lazy="selectin"
    )


class AoiLayoutRect(Base):
    __tablename__ = "aoi_layout_rects"
    __table_args__ = (
        CheckConstraint(
            "x_min < x_max AND y_min < y_max",
            name="aoi_layout_rects_order_check",
        ),
        CheckConstraint(
            "x_min > -10 AND x_max < 10 AND y_min > -10 AND y_max < 10",
            name="aoi_layout_rects_bounds_check",
        ),
        Index("idx_aoi_layout_rects_snapshot", "snapshot_id"),
        Index("idx_aoi_layout_rects_code", "semantic_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("aoi_layout_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    semantic_code: Mapped[str] = mapped_column(String(64), nullable=False)
    element_key: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("''")
    )
    x_min: Mapped[float] = mapped_column(REAL, nullable=False)
    y_min: Mapped[float] = mapped_column(REAL, nullable=False)
    x_max: Mapped[float] = mapped_column(REAL, nullable=False)
    y_max: Mapped[float] = mapped_column(REAL, nullable=False)

    snapshot: Mapped["AoiLayoutSnapshot"] = relationship(back_populates="rects")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("to_time > from_time", name="analysis_runs_time_range_check"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="analysis_runs_status_check",
        ),
        Index("idx_analysis_runs_session", "session_id", "created_at"),
        Index("idx_analysis_runs_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_presentations.id", ondelete="CASCADE")
    )
    aoi_set_id: Mapped[str] = mapped_column(
        ForeignKey("aoi_sets.id", ondelete="RESTRICT"), nullable=False
    )
    from_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    batch_watermark: Mapped[str | None] = mapped_column(
        ForeignKey("gaze_batches.id", ondelete="SET NULL")
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped["LearningSession"] = relationship()
    presentation: Mapped["ContentPresentation | None"] = relationship()
    aoi_set: Mapped["AoiSet"] = relationship()
    batch_watermark_batch: Mapped["GazeBatch | None"] = relationship()


class AoiHit(Base):
    __tablename__ = "aoi_hits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sample_id", "event_time"],
            ["gaze_samples.id", "gaze_samples.event_time"],
            ondelete="CASCADE",
        ),
        Index("idx_aoi_hits_run", "run_id"),
        Index("idx_aoi_hits_definition", "definition_id"),
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True
    )
    sample_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    definition_id: Mapped[str] = mapped_column(
        ForeignKey("aoi_definitions.id", ondelete="CASCADE"), primary_key=True
    )

    run: Mapped["AnalysisRun"] = relationship()
    definition: Mapped["AoiDefinition"] = relationship()
    sample: Mapped["GazeSample"] = relationship()


class PresentationMetric(Base):
    __tablename__ = "presentation_metrics"
    __table_args__ = (
        CheckConstraint(
            "sample_count >= 0",
            name="presentation_metrics_sample_count_check",
        ),
        CheckConstraint(
            "on_slide_count >= 0",
            name="presentation_metrics_on_slide_count_check",
        ),
        CheckConstraint(
            "dwell_ms >= 0", name="presentation_metrics_dwell_ms_check"
        ),
        CheckConstraint(
            "fixation_count >= 0",
            name="presentation_metrics_fixation_count_check",
        ),
    )

    presentation_id: Mapped[str] = mapped_column(
        ForeignKey("content_presentations.id", ondelete="CASCADE"), primary_key=True
    )
    algorithm_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_watermark: Mapped[str | None] = mapped_column(
        ForeignKey("gaze_batches.id", ondelete="SET NULL")
    )
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    on_slide_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    dwell_ms: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    fixation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    heatmap_grid: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    presentation: Mapped["ContentPresentation"] = relationship()
    batch_watermark_batch: Mapped["GazeBatch | None"] = relationship()
