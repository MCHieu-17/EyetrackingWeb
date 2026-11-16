"""Kiểm tra nội dung/header email OTP và xử lý người nhận bị SMTP từ chối."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import mailer


@pytest.fixture(autouse=True)
def _smtp_identity(monkeypatch):
    monkeypatch.setattr(settings, "smtp_user", "sender@example.com")
    monkeypatch.setattr(settings, "smtp_pass", "secret")
    monkeypatch.setattr(settings, "smtp_from", "")
    monkeypatch.setattr(settings, "smtp_from_name", "GazeEdu")
    monkeypatch.setattr(settings, "smtp_reply_to", "")
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_starttls", False)


def _plain_body(message) -> str:
    body = message.get_body(preferencelist=("plain",))
    assert body is not None
    return body.get_content()


def test_otp_message_has_transactional_headers_and_no_link():
    message = mailer._build_message("12345678@st.neu.edu.vn", "123456")

    assert message["From"] == "GazeEdu <sender@example.com>"
    assert message["To"] == "12345678@st.neu.edu.vn"
    assert message["Reply-To"] == "sender@example.com"
    assert message["Message-ID"]
    assert message["Date"]
    assert message["Auto-Submitted"] == "auto-generated"
    assert "123456" in _plain_body(message)
    # Không chèn URL vào email OTP để giảm nguy cơ bị quarantine.
    assert "http://" not in _plain_body(message)
    assert "https://" not in _plain_body(message)


def test_otp_message_honours_reply_to_override(monkeypatch):
    monkeypatch.setattr(settings, "smtp_reply_to", "support@example.com")

    message = mailer._build_message("12345678@st.neu.edu.vn", "123456")

    assert message["Reply-To"] == "support@example.com"


def test_deliver_raises_when_smtp_refuses_recipient(monkeypatch):
    refused = {"12345678@st.neu.edu.vn": (550, b"5.4.1 Recipient address rejected")}

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            pass

        def login(self, *_args):
            pass

        def send_message(self, _message):
            return refused

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)

    with pytest.raises(mailer.EmailDeliveryError):
        mailer._deliver(mailer._build_message("12345678@st.neu.edu.vn", "123456"))


def test_deliver_succeeds_when_recipient_accepted(monkeypatch):
    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            pass

        def login(self, *_args):
            pass

        def send_message(self, _message):
            return {}

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)

    mailer._deliver(mailer._build_message("12345678@st.neu.edu.vn", "123456"))
