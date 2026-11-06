FROM python:3.12-slim

# Tránh buffer log để thấy log realtime trong `docker logs`.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# LibreOffice + font cho chuyển đổi PPTX/PPT/ODP -> PDF.
# Font Noto/Liberation/Carlito/Caladea giữ đúng dấu tiếng Việt và layout.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-impress \
        libreoffice-core \
        libreoffice-common \
        fonts-noto-core \
        fonts-noto-extra \
        fonts-dejavu-core \
        fonts-liberation \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

# Cài dependencies trước (tận dụng layer cache).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code.
COPY app ./app

# Tạo user không phải root để chạy.
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/media \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

# --proxy-headers: dùng X-Forwarded-For/-Proto từ proxy tin cậy để suy ra IP
#   client thật (request.client.host) + scheme.
# --forwarded-allow-ips: CHỈ tin header từ nginx trong mạng docker nội bộ.
#   Backend không publish port ra host (chỉ nginx truy cập qua tên service),
#   nên không ai ngoài nginx gửi được request tới đây → an toàn để tin.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
