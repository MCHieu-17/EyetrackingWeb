"""Khóa API analytics: visits, summary, replay, samples, export, heatmap."""

from __future__ import annotations

import json

import pytest

from tests.conftest import execute, new_uuid
from tests.support.scenario import build_lesson_gaze

pytestmark = pytest.mark.fast


async def _data(client_factory):
    teacher_client = await client_factory()
    student_client = await client_factory()
    data = await build_lesson_gaze(
        teacher_client=teacher_client, student_client=student_client
    )
    data["teacher_client"] = teacher_client
    return data


async def test_visits_and_summary_include_short(client_factory):
    data = await _data(client_factory)
    client = data["teacher_client"]
    course_id = data["ids"]["course_id"]
    visit_id = data["visit_id"]

    visits = await client.get(f"/teacher/courses/{course_id}/visits")
    assert visits.status_code == 200, visits.text
    [visit] = visits.json()
    assert visit["id"] == visit_id
    assert visit["lessonSessionCount"] == 1
    assert visit["gazeCount"] == 3
    assert visit["onSlideGazeCount"] == 2
    assert visit["trackedDurationMs"] == 200

    summary = await client.get(f"/teacher/visits/{visit_id}/summary")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["contentViewCount"] == 1
    assert body["gazeCount"] == 3
    assert body["onSlideGazeCount"] == 2
    assert body["trackedDurationMs"] == 200
    assert body["shortViewCount"] == 1
    assert body["minDwellMs"] == 1000

    filtered = await client.get(
        f"/teacher/visits/{visit_id}/summary",
        params={"includeShort": "false"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["contentViewCount"] == 0
    assert filtered.json()["shortViewCount"] == 1
    assert filtered.json()["lessonSessionCount"] == 1

    short_filtered_visits = await client.get(
        f"/teacher/courses/{course_id}/visits",
        params={"includeShort": "false"},
    )
    assert short_filtered_visits.status_code == 200
    [visit_row] = short_filtered_visits.json()
    assert visit_row["gazeCount"] == 0
    assert visit_row["lessonSessionCount"] == 1


async def test_replay_samples_and_gaze(client_factory):
    data = await _data(client_factory)
    client = data["teacher_client"]
    visit_id = data["visit_id"]
    view_id = data["presentation_id"]

    replay = await client.get(f"/teacher/visits/{visit_id}/replay")
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["visit"]["visitId"] == visit_id
    assert body["student"]["id"] == data["student"]["id"]
    [view] = body["views"]
    assert view["contentViewId"] == view_id
    assert view["sampleCount"] == 3
    assert view["okSampleCount"] == 3
    assert view["gazeCount"] == 3
    assert view["onSlideGazeCount"] == 2
    assert view["trackedDurationMs"] == 200
    assert view["analysisStatus"] == "ready"
    assert view["analysisVersion"] == "gaze-metrics-v8"
    assert len(view["layouts"]) == 1
    assert view["layouts"][0]["slideRect"]["width"] == 0.8
    assert [item["analysisLabel"] for item in view["slideAois"]]
    assert view["aoiStats"]
    assert isinstance(body["uiAois"], list)

    samples = await client.get(
        f"/teacher/visits/{visit_id}/samples",
        params={"contentViewId": view_id},
    )
    assert samples.status_code == 200, samples.text
    page = samples.json()
    assert len(page["samples"]) == 3
    assert page["samples"][0]["offsetMs"] == 0
    assert page["nextCursor"] is None

    gaze = await client.get(f"/teacher/visits/{visit_id}/gaze")
    assert gaze.status_code == 200
    assert len(gaze.json()) == 3
    assert gaze.json()[0]["aoiLabel"] == "SLIDE_AOI_CUSTOM"

    first_gaze = await client.get(
        f"/teacher/visits/{visit_id}/gaze", params={"limit": 1}
    )
    assert first_gaze.status_code == 200
    [first_sample] = first_gaze.json()
    next_gaze = await client.get(
        f"/teacher/visits/{visit_id}/gaze",
        params={
            "limit": 1,
            "afterTime": first_sample["eventTime"],
            "afterId": first_sample["id"],
        },
    )
    assert next_gaze.status_code == 200
    [next_sample] = next_gaze.json()
    assert next_sample["id"] != first_sample["id"]
    unpaired = await client.get(
        f"/teacher/visits/{visit_id}/gaze",
        params={"afterTime": first_sample["eventTime"]},
    )
    assert unpaired.status_code == 422

    first_page = await client.get(
        f"/teacher/visits/{visit_id}/samples",
        params={
            "contentViewId": view_id,
            "afterTime": page["samples"][0]["eventTime"],
            "afterId": page["samples"][0]["id"],
            "limit": 1,
        },
    )
    assert first_page.status_code == 200
    assert first_page.json()["nextCursor"] is not None


async def test_aoi_summary_and_heatmap(client_factory):
    data = await _data(client_factory)
    client = data["teacher_client"]
    course_id = data["ids"]["course_id"]

    summary = await client.post(
        f"/teacher/courses/{course_id}/analytics/aoi-summary",
        json={"includeShort": True},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["totals"]["contentViewCount"] == 1
    assert body["totals"]["gazeSampleCount"] == 3
    assert body["totals"]["onSlideGazeCount"] == 2
    assert body["totals"]["trackedDurationMs"] == 200
    assert body["meta"]["analysisVersion"] == "gaze-metrics-v8"
    labels = {item["label"] for item in body["byAoi"]}
    assert {"SLIDE_AOI_CUSTOM", "SLIDE_AOI_TEXT2", "Header"} <= labels

    heatmap = await client.post(
        f"/teacher/courses/{course_id}/analytics/heatmap",
        json={"slideId": data["slide_id"]},
    )
    assert heatmap.status_code == 200, heatmap.text
    grid = heatmap.json()["grid"]
    assert len(grid) == 24
    assert all(len(row) == 24 for row in grid)
    assert heatmap.json()["onSlideSampleCount"] == 2
    assert heatmap.json()["analyzedViewCount"] == 1


async def test_aoi_summary_aggregate_matches_buckets(client_factory):
    """Tổng hợp SQL phải khớp bất biến với các bucket và bỏ entry rỗng."""
    data = await _data(client_factory)
    client = data["teacher_client"]
    course_id = data["ids"]["course_id"]
    view_id = new_uuid()
    stats = {
        "SLIDE_AOI_CUSTOM": {"ms": 120, "samples": 2},
        "Header": {"ms": 80, "samples": 1},
        "ZeroLabel": {"ms": 0, "samples": 0},
        "BadLabel": 5,
    }
    await execute(
        """
        INSERT INTO content_views
            (id, session_id, slide_id, surface, sequence_no, started_at,
             ended_at, gaze_count, on_slide_gaze_count, tracked_duration_ms,
             fixation_count, heatmap_grid, analysis_status, analysis_version,
             aoi_stats)
        VALUES
            (:id, :session, NULL, 'quiz', 99, now(), now(), 3, 0, 500, 1,
             '[]'::jsonb, 'ready', 'gaze-metrics-v8', CAST(:stats AS jsonb))
        """,
        {
            "id": view_id,
            "session": data["session_id"],
            "stats": json.dumps(stats),
        },
    )

    summary = await client.post(
        f"/teacher/courses/{course_id}/analytics/aoi-summary",
        json={"includeShort": True},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    totals = body["totals"]
    assert totals["contentViewCount"] == 2
    assert totals["labeledDurationMs"] == 400

    labels = {item["label"]: item for item in body["byAoi"]}
    assert "ZeroLabel" not in labels
    assert "BadLabel" not in labels
    assert labels["SLIDE_AOI_CUSTOM"]["durationMs"] == 120
    assert labels["SLIDE_AOI_CUSTOM"]["studentCount"] == 1
    assert labels["SLIDE_AOI_CUSTOM"]["slideCount"] == 1
    assert labels["Header"]["durationMs"] == 180

    # Bất biến: mọi bucket cộng lại bằng tổng thời lượng đã gắn nhãn.
    for key in ("byLesson", "byStudent", "byVisit"):
        assert sum(item["durationMs"] for item in body[key]) == 400
    # View quiz không có slide nên không được xuất hiện trong bySlide.
    assert [item["slideId"] for item in body["bySlide"]] == [data["slide_id"]]

    filters = {
        "visit": {"visitIds": [data["visit_id"]]},
        "student": {"studentIds": [data["student"]["id"]]},
        "lesson": {"lessonIds": [data["lesson_id"]]},
        "quiz": {"surface": "quiz"},
        "future": {"from": "2999-01-01T00:00:00Z"},
        "short": {"includeShort": False},
    }
    expected = {
        "visit": (2, 2),
        "student": (2, 2),
        "lesson": (2, 2),
        "quiz": (1, 1),
        "future": (0, 0),
        "short": (0, 2),
    }
    for name, extra in filters.items():
        response = await client.post(
            f"/teacher/courses/{course_id}/analytics/aoi-summary",
            json={"includeShort": True, **extra},
        )
        assert response.status_code == 200, f"{name}: {response.text}"
        result = response.json()
        views, shorts = expected[name]
        assert result["totals"]["contentViewCount"] == views, name
        assert result["meta"]["shortViewCount"] == shorts, name
        if name == "quiz":
            assert result["bySlide"] == []
            assert {item["label"] for item in result["byAoi"]} == {
                "SLIDE_AOI_CUSTOM",
                "Header",
            }


async def test_visit_export_ndjson(client_factory, monkeypatch):
    from app.services.analysis import export as export_service

    monkeypatch.setattr(export_service, "EXPORT_PAGE_SIZE", 1)
    data = await _data(client_factory)
    response = await data["teacher_client"].get(
        f"/teacher/visits/{data['visit_id']}/export"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in response.headers["content-disposition"]
    lines = [line for line in response.text.splitlines() if line.strip()]
    assert len(lines) >= 1
    payloads = []
    for line in lines:
        payload = json.loads(line)
        assert isinstance(payload, dict)
        payloads.append(payload)
    visit_samples = [item for item in payloads if item["type"] == "sample"]
    assert len(visit_samples) == 3
    assert visit_samples[0]["contentViewId"] == data["presentation_id"]
    assert visit_samples[0]["lessonId"] == data["lesson_id"]
    assert visit_samples[0]["slideId"] == data["slide_id"]

    lesson_response = await data["teacher_client"].get(
        f"/teacher/lessons/{data['lesson_id']}/export",
        params={"scope": "slide"},
    )
    assert lesson_response.status_code == 200
    lesson_payloads = [
        json.loads(line)
        for line in lesson_response.text.splitlines()
        if line.strip()
    ]
    lesson_samples = [item for item in lesson_payloads if item["type"] == "sample"]
    assert len(lesson_samples) == 3
    assert lesson_samples[0]["contentViewId"] == data["presentation_id"]
