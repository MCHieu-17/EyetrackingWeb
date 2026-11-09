import pymupdf

from app.services import slide_aoi


def _make_pdf(
    *, text: bool = False, image: bool = False, table: bool = False
) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=800, height=600)
    if text:
        page.insert_text((50, 50), "Hello world, this is a text block.")
    if image:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
        pix.set_rect(pix.irect, (255, 0, 0))
        page.insert_image(
            pymupdf.Rect(400, 300, 600, 500), stream=pix.tobytes("png")
        )
    if table:
        x0, y0, x1, y1 = 50, 200, 350, 320
        for x in (x0, (x0 + x1) // 2, x1):
            page.draw_line((x, y0), (x, y1), width=1.5)
        for y in (y0, (y0 + y1) // 2, y1):
            page.draw_line((x0, y), (x1, y), width=1.5)
        page.insert_text((60, 230), "A1")
        page.insert_text((210, 230), "B1")
        page.insert_text((60, 290), "A2")
        page.insert_text((210, 290), "B2")
    data = doc.tobytes()
    doc.close()
    return data


def _extract(data: bytes):
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        page = doc.load_page(0)
        return slide_aoi.extract_page_aois(page, 1)


def test_extract_three_layout_aois():
    aois = _extract(_make_pdf(text=True, image=True, table=True))
    by_kind = {item.kind: item for item in aois}
    assert set(by_kind) == {"image", "text", "table"}
    assert by_kind["image"].name == "IMAGE"
    assert by_kind["text"].name == "TEXT"
    assert by_kind["table"].name == "TABLE"
    assert by_kind["image"].x_min < by_kind["image"].x_max
    assert by_kind["text"].y_min < by_kind["text"].y_max
    assert by_kind["table"].x_min < by_kind["table"].x_max


def test_extract_text_only():
    aois = _extract(_make_pdf(text=True))
    assert [item.kind for item in aois] == ["text"]


def test_extract_multiple_text_blocks_are_separate():
    doc = pymupdf.open()
    page = doc.new_page(width=800, height=600)
    page.insert_text((50, 50), "First text block with enough characters to pass the area filter")
    page.insert_text((50, 300), "Second text block with enough characters to pass the area filter")
    data = doc.tobytes()
    doc.close()

    aois = _extract(data)
    assert [item.kind for item in aois] == ["text", "text"]
    assert [item.name for item in aois] == ["TEXT", "TEXT"]
    assert len({item.code for item in aois}) == 2


def test_extract_image_only():
    aois = _extract(_make_pdf(image=True))
    assert [item.kind for item in aois] == ["image"]


def test_extract_table_only():
    aois = _extract(_make_pdf(table=True))
    assert [item.kind for item in aois] == ["table"]


def test_extract_blank_page():
    assert _extract(_make_pdf()) == []


def test_candidates_from_metadata_requires_current_version():
    old = {
        "aoi_candidates": [
            {
                "code": "x",
                "name": "x",
                "kind": "text",
                "xMin": 0,
                "yMin": 0,
                "xMax": 1,
                "yMax": 1,
            }
        ]
    }
    assert slide_aoi.candidates_from_metadata(old) == []
    current = {**old, "aoi_layout_version": slide_aoi.AOI_LAYOUT_VERSION}
    assert len(slide_aoi.candidates_from_metadata(current)) == 1
