"""Khóa pipeline gaze → slide/AOI/metrics qua worker thật."""

from __future__ import annotations

import pytest

from tests.conftest import fetch_all, fetch_one
from tests.support.scenario import build_lesson_gaze

pytestmark = pytest.mark.fast


async def test_metrics_slide_mapping_labels_heatmap_and_dwell(
    client_factory,
):
    teacher_client = await client_factory()
    student_client = await client_factory()
    data = await build_lesson_gaze(
        teacher_client=teacher_client, student_client=student_client
    )
    view = await fetch_one(
        "SELECT * FROM content_views WHERE id = :id",
        {"id": data["presentation_id"]},
    )
    assert view["analysis_status"] == "ready"
    assert view["analysis_version"] == "gaze-metrics-v8"
    assert view["gaze_count"] == 3
    assert view["on_slide_gaze_count"] == 2
    assert view["tracked_duration_ms"] == 200
    assert view["fixation_count"] == 0
    assert len(view["heatmap_grid"]) == 24
    assert all(len(row) == 24 for row in view["heatmap_grid"])
    assert view["heatmap_grid"][4][4] == 1
    assert view["heatmap_grid"][15][15] == 1
    assert sum(sum(row) for row in view["heatmap_grid"]) == 2

    labels = {
        row["sequence"]: row["aoi_label"]
        for row in await fetch_all(
            "SELECT sequence, aoi_label FROM gaze_samples "
            "WHERE content_view_id = :id ORDER BY sequence",
            {"id": data["presentation_id"]},
        )
    }
    assert labels == {
        0: "SLIDE_AOI_CUSTOM",
        1: "SLIDE_AOI_TEXT2",
        2: "Header",
    }
    stats = view["aoi_stats"]
    assert stats["SLIDE_AOI_CUSTOM"] == {"ms": 0, "samples": 1}
    assert stats["SLIDE_AOI_TEXT2"] == {"ms": 100, "samples": 1}
    assert stats["Header"] == {"ms": 100, "samples": 1}


async def test_metrics_missing_layout_marks_quality_flag(client_factory):
    teacher_client = await client_factory()
    student_client = await client_factory()
    data = await build_lesson_gaze(
        teacher_client=teacher_client,
        student_client=student_client,
        with_layout=False,
        with_slide_aois=False,
    )
    view = await fetch_one(
        "SELECT * FROM content_views WHERE id = :id",
        {"id": data["presentation_id"]},
    )
    assert view["on_slide_gaze_count"] == 0
    assert view["tracked_duration_ms"] == 200
    samples = await fetch_all(
        "SELECT slide_x, slide_y, aoi_label, quality_flags FROM gaze_samples "
        "WHERE content_view_id = :id ORDER BY sequence",
        {"id": data["presentation_id"]},
    )
    assert all(sample["slide_x"] is None and sample["slide_y"] is None for sample in samples)
    assert all(sample["aoi_label"] == "UI_NO_LABEL" for sample in samples)
    assert all(sample["quality_flags"]["layout_missing"] is True for sample in samples)
