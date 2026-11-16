from app.models.aoi import Aoi
from app.services.metrics import (
    SLIDE_NO_LABEL,
    UI_NO_LABEL,
    _slide_aoi_label,
    _slide_label_text,
    _ui_aoi_label,
    map_viewport_to_slide,
)


def _aoi(
    code: str,
    kind: str,
    geom: dict,
    *,
    name: str | None = None,
    label: str | None = None,
    container: bool = False,
) -> Aoi:
    return Aoi(
        id=code,
        slide_id="s",
        code=code,
        name=name or code,
        label=label,
        geometry=geom,
        is_container=container,
        kind=kind,
        is_active=True,
    )


def _ui_aoi(
    code: str,
    name: str,
    geom: dict,
    *,
    kind: str = "ui",
    container: bool = False,
) -> Aoi:
    return Aoi(
        id=code,
        slide_id=None,
        ui_schema="reader-v1",
        code=code,
        name=name,
        geometry=geom,
        is_container=container,
        kind=kind,
        is_active=True,
    )


def test_slide_returns_one_best_leaf_label():
    aois = [
        _aoi(
            "slide_1",
            "system",
            {"xMin": 0, "yMin": 0, "xMax": 1, "yMax": 1},
            container=True,
        ),
        _aoi(
            "img",
            "image",
            {"xMin": 0.1, "yMin": 0.1, "xMax": 0.9, "yMax": 0.9},
            label="AOI_BANGBIEU",
        ),
        _aoi(
            "text",
            "text",
            {"xMin": 0.2, "yMin": 0.2, "xMax": 0.8, "yMax": 0.8},
            label="AOI_THANHCHAT",
        ),
        _aoi("no_label", "system", {}),
    ]
    # Text thắng image; nhãn giáo viên được giữ nguyên, không trả container.
    assert _slide_aoi_label(0.5, 0.5, aois) == "SLIDE_AOI_THANHCHAT"


def test_slide_label_text_keeps_upper_snake_case():
    # Nhãn giáo viên chỉ gồm A-Z, 0-9, _ sau khi uppercase.
    assert _slide_label_text("aoi_thanhchat", "fallback") == "AOI_THANHCHAT"
    assert _slide_label_text("AOI_BANG_BIEU", "fallback") == "AOI_BANG_BIEU"
    assert _slide_label_text(None, "custom_code") == "CUSTOM_CODE"


def test_slide_no_label_when_inside_but_outside_all_leaf():
    aois = [
        _aoi(
            "text",
            "text",
            {"xMin": 0.1, "yMin": 0.1, "xMax": 0.2, "yMax": 0.2},
            label="AOI_1",
        ),
        _aoi("no_label", "system", {}),
    ]
    assert _slide_aoi_label(0.8, 0.8, aois) == SLIDE_NO_LABEL


def test_viewport_mapping_and_ui_smallest_label():
    assert map_viewport_to_slide(
        0.5, 0.5, {"left": 0, "top": 0, "width": 1, "height": 1}
    ) == (0.5, 0.5)

    aois = [
        _ui_aoi(
            "chatbot",
            "Trợ lý học tập",
            {"selector": "[data-aoi='chatbot']"},
        ),
        _ui_aoi(
            "chat-send",
            "Nút gửi",
            {"selector": "[data-aoi='chat-send']"},
        ),
    ]
    elements = [
        {"code": "chatbot", "xMin": 0.6, "yMin": 0.0, "xMax": 1.0, "yMax": 1.0},
        {"code": "chat-send", "xMin": 0.9, "yMin": 0.8, "xMax": 0.98, "yMax": 0.9},
    ]
    assert _ui_aoi_label(0.94, 0.85, aois, elements) == "Nút gửi"
    assert _ui_aoi_label(0.7, 0.5, aois, elements) == "Trợ lý học tập"
    assert _ui_aoi_label(0.1, 0.1, aois, elements) == UI_NO_LABEL


def test_ui_container_is_skipped():
    aois = [
        _ui_aoi(
            "chat-container",
            "Khung chat",
            {
                "anchor": "chatbot",
                "xMin": 0.0,
                "yMin": 0.0,
                "xMax": 1.0,
                "yMax": 1.0,
            },
            kind="custom",
            container=True,
        ),
        _ui_aoi(
            "chat-send",
            "Nút gửi",
            {"selector": "[data-aoi='chat-send']"},
        ),
        _ui_aoi(
            "chatbot",
            "Trợ lý học tập",
            {"selector": "[data-aoi='chatbot']"},
        ),
    ]
    elements = [
        {"code": "chatbot", "xMin": 0.6, "yMin": 0.0, "xMax": 1.0, "yMax": 1.0},
        {"code": "chat-send", "xMin": 0.9, "yMin": 0.8, "xMax": 0.98, "yMax": 0.9},
    ]
    # Container phủ vùng chat nhưng không được làm nhãn.
    assert _ui_aoi_label(0.8, 0.5, aois, elements) == "Trợ lý học tập"
    assert _ui_aoi_label(0.94, 0.85, aois, elements) == "Nút gửi"


def test_ui_custom_wins_over_component():
    aois = [
        _ui_aoi(
            "chatbot",
            "Trợ lý học tập",
            {"selector": "[data-aoi='chatbot']"},
        ),
        _ui_aoi(
            "custom",
            "Vùng chat của tôi",
            {
                "anchor": "chatbot",
                "xMin": 0.0,
                "yMin": 0.0,
                "xMax": 1.0,
                "yMax": 1.0,
            },
            kind="custom",
        ),
    ]
    elements = [
        {"code": "chatbot", "xMin": 0.6, "yMin": 0.0, "xMax": 1.0, "yMax": 1.0},
    ]
    assert _ui_aoi_label(0.8, 0.5, aois, elements) == "Vùng chat của tôi"
