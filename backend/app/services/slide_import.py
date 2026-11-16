"""Chuyển đổi và kiểm tra tài liệu slide trước khi lưu PDF.

Hỗ trợ PDF, PPTX, PPT và ODP. Các định dạng Impress được chuyển sang PDF bằng
LibreOffice headless; PDF được giữ nguyên. Mọi file đều được kiểm tra magic
bytes, số trang và giới hạn kích thước trước khi ghi vào storage.
"""

from __future__ import annotations

import io
import logging
import os
import signal
import subprocess
import tempfile
import zipfile
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PyPdfError

from app.core.config import settings

logger = logging.getLogger(__name__)

FORMAT_BY_EXTENSION = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".ppt": "ppt",
    ".odp": "odp",
}
MIME_BY_FORMAT = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ppt": "application/vnd.ms-powerpoint",
    "odp": "application/vnd.oasis.opendocument.presentation",
}


class SlideImportError(RuntimeError):
    """File không hợp lệ hoặc không chuyển đổi được."""


def mime_for_format(fmt: str) -> str:
    return MIME_BY_FORMAT[fmt]


def detect_format(filename: str, mime: str | None, data: bytes) -> str:
    """Nhận diện định dạng bằng magic bytes, không tin MIME của client."""
    del mime  # MIME client chỉ là gợi ý; magic bytes mới quyết định.
    ext = Path(filename or "").suffix.lower()

    if data.startswith(b"%PDF"):
        return "pdf"

    if data.startswith(b"PK\x03\x04"):
        # Không tin đuôi file: ZIP có thể là DOCX/XLSX hoặc file hỏng.
        if _is_odp(data):
            return "odp"
        if _is_pptx(data):
            return "pptx"
        raise SlideImportError("File ZIP không phải PPTX/ODP hợp lệ.")

    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if ext == ".ppt":
            return "ppt"
        raise SlideImportError("File PowerPoint cũ phải có đuôi .ppt.")

    if ext in FORMAT_BY_EXTENSION:
        raise SlideImportError("Nội dung file không khớp định dạng đã chọn.")

    raise SlideImportError("Chỉ hỗ trợ PDF, PPTX, PPT và ODP.")


def _is_pptx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "ppt/presentation.xml" in names:
                return True
            if "[Content_Types].xml" in names:
                content = archive.read("[Content_Types].xml")
                return b"presentationml.presentation.main+xml" in content
    except (zipfile.BadZipFile, KeyError):
        return False
    return False


def _is_odp(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "mimetype" in names:
                return (
                    archive.read("mimetype").strip()
                    == b"application/vnd.oasis.opendocument.presentation"
                )
            return "content.xml" in names and "META-INF/manifest.xml" in names
    except (zipfile.BadZipFile, KeyError):
        return False


def convert_to_pdf(data: bytes, fmt: str, filename: str) -> bytes:
    """Trả về PDF chuẩn hóa. PDF đi thẳng, định dạng khác qua LibreOffice."""
    if fmt == "pdf":
        return data
    if fmt not in {"pptx", "ppt", "odp"}:
        raise SlideImportError("Định dạng không hỗ trợ chuyển đổi.")

    # Dùng đuôi theo định dạng đã nhận diện, không theo tên file gốc.
    suffix = f".{fmt}"
    with tempfile.TemporaryDirectory(prefix="slide-import-") as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / f"input{suffix}"
        source.write_bytes(data)
        profile = tmp_path / "lo-profile"
        profile.mkdir()

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)
        command = [
            settings.libreoffice_binary,
            "--headless",
            "--norestore",
            "--invisible",
            "--nodefault",
            "--nolockcheck",
            "--nologo",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            "pdf:impress_pdf_Export",
            "--outdir",
            str(tmp_path),
            str(source),
        ]

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise SlideImportError(
                "Máy chủ chưa cài LibreOffice để chuyển đổi slide."
            ) from exc

        try:
            stdout, stderr = process.communicate(
                timeout=settings.libreoffice_timeout_seconds
            )
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise SlideImportError(
                "Chuyển đổi slide quá thời gian cho phép."
            ) from None

        if process.returncode != 0:
            detail = (stderr or stdout or b"").decode("utf-8", "ignore")[-500:]
            logger.warning("LibreOffice convert failed: %s", detail)
            raise SlideImportError(
                "LibreOffice không chuyển đổi được file. "
                "Hãy kiểm tra file có bị hỏng hoặc đặt mật khẩu không."
            )

        output = tmp_path / "input.pdf"
        if not output.is_file():
            candidates = sorted(tmp_path.glob("*.pdf"))
            if not candidates:
                raise SlideImportError("LibreOffice không tạo được PDF.")
            output = candidates[0]
        return output.read_bytes()


def validate_pdf(data: bytes) -> int:
    """Kiểm tra PDF và trả về số trang."""
    if len(data) > settings.max_pdf_bytes:
        limit = settings.max_pdf_bytes // (1024 * 1024)
        raise SlideImportError(f"PDF vượt quá {limit}MB cho phép.")
    if not data.startswith(b"%PDF"):
        raise SlideImportError("File không phải PDF hợp lệ.")

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, ValueError, OSError) as exc:
        raise SlideImportError(f"Không đọc được PDF: {exc}") from exc

    try:
        if reader.is_encrypted:
            raise SlideImportError(
                "PDF đang bị bảo vệ bằng mật khẩu — hãy gỡ mật khẩu trước."
            )
        page_count = len(reader.pages)
        if page_count == 0:
            raise SlideImportError("PDF không có trang nào.")
        if page_count > settings.max_slide_pages:
            raise SlideImportError(
                f"Tài liệu có {page_count} trang, vượt quá "
                f"{settings.max_slide_pages} trang cho phép."
            )
        for page_no, page in enumerate(reader.pages, start=1):
            box = page.mediabox
            if float(box.width) * float(box.height) > settings.max_slide_render_pixels:
                raise SlideImportError(
                    f"Trang {page_no} có kích thước quá lớn."
                )
        return page_count
    except SlideImportError:
        raise
    except PyPdfError as exc:
        raise SlideImportError(f"Không đọc được PDF: {exc}") from exc
