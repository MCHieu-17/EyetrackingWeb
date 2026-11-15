"""Tests cho ingest: giữ kết quả từng slide khi batch lỗi một phần."""

from app.services.ingest import Ingestion, VLMUnavailableError


def _ingestion() -> Ingestion:
    # Bỏ qua __init__ (DB/VLM) — các test dưới chỉ kiểm tra logic batch.
    return object.__new__(Ingestion)


def _slide(slide_id: str) -> dict:
    return {"slide_id": slide_id, "index_status": "pending"}


def test_process_slides_returns_mixed_counts(monkeypatch):
    ingestion = _ingestion()

    def fake_embed(slide):
        if slide["slide_id"] == "bad":
            raise VLMUnavailableError("VLM tạm thời không khả dụng")

    monkeypatch.setattr(ingestion, "_embed_slide", fake_embed)

    processed, failed, errors = ingestion._process_slides(
        [_slide("ok"), _slide("bad")]
    )

    assert processed == 1
    assert failed == 1
    assert errors == ["bad: VLM tạm thời không khả dụng"]


def test_process_slides_raises_only_when_all_vlm_failed(monkeypatch):
    ingestion = _ingestion()

    def fake_embed(slide):
        raise VLMUnavailableError("VLM tạm thời không khả dụng")

    monkeypatch.setattr(ingestion, "_embed_slide", fake_embed)

    try:
        ingestion._process_slides([_slide("bad-1"), _slide("bad-2")])
    except VLMUnavailableError:
        pass
    else:
        raise AssertionError("phải báo lỗi transport khi không slide nào thành công")


def test_embed_slides_skips_already_ready_slides(monkeypatch):
    ingestion = _ingestion()
    slides = [
        {"slide_id": "ready", "index_status": "ready"},
        {"slide_id": "pending", "index_status": "pending"},
    ]
    processed: list[list[dict]] = []

    monkeypatch.setattr(
        ingestion,
        "_load_slides",
        lambda slide_ids: [s for s in slides if s["slide_id"] in slide_ids],
    )

    def fake_process(items):
        processed.append(list(items))
        return len(items), 0, []

    monkeypatch.setattr(ingestion, "_process_slides", fake_process)

    assert ingestion.embed_slides(["ready", "pending"]) == (1, 0, [])
    assert [slide["slide_id"] for slide in processed[0]] == ["pending"]

    assert ingestion.embed_slides(["ready"]) == (0, 0, [])
    assert len(processed) == 1
