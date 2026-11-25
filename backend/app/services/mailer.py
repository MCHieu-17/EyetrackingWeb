"""Gửi email OTP đăng nhập qua SMTP.

Toàn bộ thao tác SMTP chạy trong thread (`asyncio.to_thread`) để không chặn
event loop. Không log mã OTP ở bất kỳ mức log nào; log chỉ gồm host/port và
loại lỗi để tránh lộ PII.

Email OTP là giao dịch một lần, không phải email marketing. Nội dung được giữ
tối giản, không chèn link để giảm khả năng bị bộ lọc thư rác của Microsoft 365
gắn cờ phishing — đây là nguyên nhân phổ biến khiến sinh viên không thấy mã
trong hộp thư Outlook lần đầu.
"""

from __future__ import annotations

import asyncio
import html
import logging
import math
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from app.core.config import settings

logger = logging.getLogger("app.mailer")

OTP_SUBJECT = "[Eyetracking] Mã xác nhận đăng nhập"


class EmailDeliveryError(Exception):
    """Không gửi được email OTP (SMTP lỗi, timeout, xác thực thất bại...)."""


class EmailDeliveryNotConfigured(EmailDeliveryError):
    """SMTP chưa được cấu hình trên server."""


def _expiry_minutes() -> int:
    return max(1, math.ceil(settings.otp_ttl_seconds / 60))


def _sender_domain() -> str | None:
    """Domain của địa chỉ From, dùng cho Message-ID."""
    _, _, domain = settings.smtp_from_resolved.partition("@")
    return domain.strip() or None


def _build_message(email: str, code: str) -> EmailMessage:
    minutes = _expiry_minutes()
    message = EmailMessage()
    message["Subject"] = OTP_SUBJECT
    message["From"] = formataddr(
        (settings.smtp_from_name, settings.smtp_from_resolved)
    )
    message["To"] = email
    # Các header chuẩn của thư giao dịch. Một số relay/spam filter (nhất là
    # Microsoft 365) đánh giá thấp email thiếu Date/Message-ID.
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=_sender_domain())
    message["Reply-To"] = settings.smtp_reply_to_resolved
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"

    text_body = (
        "Xin chào,\n\n"
        f"Mã xác nhận đăng nhập Eyetracking của bạn là: {code}\n\n"
        f"Mã có hiệu lực trong {minutes} phút và chỉ dùng được một lần.\n"
        "Nếu thư nằm trong Thư rác, hãy chọn \"Không phải thư rác\" để nhận\n"
        "các mã đăng nhập sau.\n"
        "Nếu bạn không yêu cầu đăng nhập, hãy bỏ qua email này.\n\n"
        "Trân trọng,\n"
        "Eyetracking\n"
        "Đại học Kinh tế Quốc dân\n"
    )
    # Không chèn URL vào email OTP: thư có mã 6 số kèm link lạ thường bị
    # Microsoft 365 quarantine ở lần gửi đầu tiên từ một người gửi mới.
    html_body = f"""\
<!doctype html>
<html lang="vi">
  <body style="margin:0;padding:24px;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:480px;margin:0 auto;">
      <p style="margin:0 0 8px;">Xin chào,</p>
      <p style="margin:0 0 16px;">Mã xác nhận đăng nhập Eyetracking của bạn là:</p>
      <div style="font-size:32px;font-weight:700;letter-spacing:8px;text-align:center;
                  padding:16px;border:1px solid #dbeafe;border-radius:8px;color:#1d4ed8;">
        {html.escape(code)}
      </div>
      <p style="margin:16px 0 8px;">
        Mã có hiệu lực trong <strong>{minutes} phút</strong> và chỉ dùng được một lần.
      </p>
      <p style="margin:0 0 16px;color:#4b5563;">
        Nếu thư nằm trong Thư rác, hãy chọn <strong>Không phải thư rác</strong>
        để nhận các mã đăng nhập sau. Nếu bạn không yêu cầu đăng nhập, hãy bỏ
        qua email này.
      </p>
      <p style="margin:24px 0 0;color:#6b7280;font-size:13px;">
        Trân trọng,<br />Eyetracking<br />Đại học Kinh tế Quốc dân
      </p>
    </div>
  </body>
</html>
"""
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def _deliver(message: EmailMessage) -> None:
    host = settings.smtp_host.strip()
    port = settings.smtp_port
    refused: dict = {}
    try:
        if settings.smtp_use_ssl:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                host, port, timeout=settings.smtp_timeout_seconds
            )
        else:
            client = smtplib.SMTP(
                host, port, timeout=settings.smtp_timeout_seconds
            )
        with client:
            if not settings.smtp_use_ssl and settings.smtp_starttls:
                client.starttls()
            if settings.smtp_user and settings.smtp_pass:
                client.login(settings.smtp_user, settings.smtp_pass)
            refused = client.send_message(message)
    except Exception as exc:  # noqa: BLE001 — mọi lỗi SMTP đều thành EmailDeliveryError
        # Chỉ log loại lỗi + host/port; không log địa chỉ người nhận hay mã OTP.
        logger.warning(
            "gửi email OTP thất bại smtp=%s:%s error=%s",
            host,
            port,
            type(exc).__name__,
        )
        raise EmailDeliveryError("Không gửi được email xác nhận") from exc

    # smtplib chỉ ném lỗi khi toàn bộ lô bị từ chối; trường hợp một người nhận
    # bị từ chối (ví dụ 550 5.4.1 của Exchange Online) được trả trong dict.
    # Bỏ qua dict này sẽ khiến API báo 200 trong khi sinh viên không nhận được
    # email — đúng lỗi "gửi mã mà không thấy thư".
    if refused:
        domains = sorted(
            {
                address.rpartition("@")[2].lower() or "unknown"
                for address in refused
            }
        )
        codes = sorted(
            {
                str(info[0])
                for info in refused.values()
                if isinstance(info, tuple) and info
            }
        )
        logger.warning(
            "SMTP từ chối người nhận smtp=%s:%s domains=%s codes=%s",
            host,
            port,
            ",".join(domains),
            ",".join(codes) or "unknown",
        )
        raise EmailDeliveryError("Không gửi được email xác nhận")

    logger.info("đã gửi email OTP smtp=%s:%s", host, port)


async def send_otp_email(email: str, code: str) -> None:
    """Gửi mã OTP tới `email`; ném lỗi typed nếu SMTP chưa cấu hình/lỗi."""
    if not settings.smtp_configured or not settings.smtp_from_resolved:
        raise EmailDeliveryNotConfigured("SMTP chưa được cấu hình")
    message = _build_message(email, code)
    await asyncio.to_thread(_deliver, message)
