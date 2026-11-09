from app.core.helpers import escape_like


def test_escape_like_escapes_backslash():
    assert escape_like("a\\b") == "a\\\\b"


def test_escape_like_escapes_percent():
    assert escape_like("100%") == "100\\%"


def test_escape_like_escapes_underscore():
    assert escape_like("a_b") == "a\\_b"


def test_escape_like_keeps_plain_text():
    assert escape_like("Khóa học 1") == "Khóa học 1"
