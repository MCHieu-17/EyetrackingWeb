from app.services.ingest import Ingestion, VLMOutput


def test_add_context_includes_metadata():
    slide = {
        "course_title": "Cơ sở dữ liệu",
        "module_title": "Chương 1",
        "lesson_title": "Bài 1",
        "slide_index": 2,
    }
    content = Ingestion._add_context(None, slide, "# Nội dung")
    assert "Môn học: Cơ sở dữ liệu" in content
    assert "Chương: Chương 1" in content
    assert "Bài học: Bài 1" in content
    assert "Slide: 2" in content
    assert content.endswith("# Nội dung")


def test_add_context_without_metadata():
    content = Ingestion._add_context(None, {}, "# Nội dung")
    assert content == "# Nội dung"


def test_vlm_output_model():
    output = VLMOutput(transcript="# Slide")
    assert output.transcript == "# Slide"
