"""Khóa API analytics: visits, summary, replay, samples, export, heatmap."""

from __future__ import annotations

import json

import pytest

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


async def test_visit_export_ndjson(client_factory):
    data = await _data(client_factory)
    response = await data["teacher_client"].get(
        f"/teacher/visits/{data['visit_id']}/export"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in response.headers["content-disposition"]
    lines = [line for line in response.text.splitlines() if line.strip()]
    assert len(lines) >= 1
    for line in lines:
        payload = json.loads(line)
        assert isinstance(payload, dict)
