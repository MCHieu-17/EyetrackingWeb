"""Tải weights (mediapipe + unigaze) vào WEIGHTS_DIR lúc khởi động container.

Chạy: entrypoint.sh gọi `python -m scripts.download_weights`; khi dev có thể
chạy trực tiếp `python scripts/download_weights.py`.
"""

import hashlib
import os
import re
import sys
import urllib.request
from pathlib import Path

# Cho phép chạy trực tiếp file script (khi đó sys.path[0] là scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import WEIGHTS_DIR as _WEIGHTS_DIR  # noqa: E402

WEIGHTS_DIR = str(_WEIGHTS_DIR)

FILES = [
    {
        "name": "mediapipe.tflite",
        "sources": [
            ("drive", "1SOIwZEVFdZdLA4d_4hgEqhPaz1gp1jjV"),
            ("url", "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"),
        ],
        "min_size": 50_000,
    },
    {
        # Đổi model: tên file phải trùng key trong unigaze.loader.MODEL_INDEX
        # (xem app/services/pipeline.py). `min_size` chặn file tải dở.
        "name": "unigaze_b16_joint.safetensors",
        "sources": [
            ("url", "https://huggingface.co/UniGaze/UniGaze-models/resolve/main/unigaze_b16_joint.safetensors"),
        ],
        "min_size": 340_000_000,
        # Pin SHA256 để build/khởi động reproducible (file HF cố định theo revision).
        "sha256": "2580d707b1395840ecabe7906e2cb35705f38c4ddb0be9c3c38ebb2d5546ffb8",
    },
]

UA = "Mozilla/5.0 (compatible; GazeAPI/1.0)"


def http(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def stream_to_file(resp, dest):
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)


def download_url(url, dest):
    stream_to_file(http(url), dest)


def download_drive(file_id, dest):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = http(url)
    ctype = resp.headers.get_content_type()
    if ctype and ctype.startswith("text/html"):
        html = resp.read().decode("utf-8", "replace")
        m = re.search(r'name="confirm" value="([^"]+)"', html)
        if not m:
            raise RuntimeError("không lấy được token xác nhận của Google Drive")
        params = f"confirm={m.group(1)}&id={file_id}"
        u = re.search(r'name="uuid" value="([^"]+)"', html)
        if u:
            params += f"&uuid={u.group(1)}"
        download_url(f"https://drive.google.com/uc?export=download&{params}", dest)
    else:
        stream_to_file(resp, dest)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure(name, sources, min_size, sha256=None):
    dest = os.path.join(WEIGHTS_DIR, name)
    if os.path.isfile(dest) and os.path.getsize(dest) >= min_size:
        if sha256 is None or sha256_of(dest) == sha256:
            print(f"[weights] {name}: co san ({os.path.getsize(dest):,} bytes)")
            return True
        print(f"[weights] {name}: checksum khong khop, tai lai")
        os.remove(dest)
    for kind, value in sources:
        try:
            if kind == "drive":
                print(f"[weights] {name}: dang tai tu Google Drive ...")
                download_drive(value, dest)
            else:
                print(f"[weights] {name}: dang tai tu {value} ...")
                download_url(value, dest)
            size = os.path.getsize(dest)
            if size >= min_size and (sha256 is None or sha256_of(dest) == sha256):
                print(f"[weights] {name}: xong ({size:,} bytes)")
                return True
            if size < min_size:
                print(f"[weights] {name}: file qua nho ({size:,} bytes), thu nguon khac")
            else:
                print(f"[weights] {name}: checksum khong khop, thu nguon khac")
        except Exception as e:
            print(f"[weights] {name}: loi tai ({kind}): {e}")
        finally:
            if os.path.exists(dest + ".part"):
                os.remove(dest + ".part")
            if os.path.isfile(dest) and os.path.getsize(dest) < min_size:
                os.remove(dest)
    return False


def main():
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    ok = True
    for f in FILES:
        ok = ensure(**f) and ok
    if not ok:
        print("LOI: khong tai du weights. Kiem tra mang va link Google Drive.", file=sys.stderr)
        sys.exit(1)
    print("[weights] Tat ca weights da san sang.")


if __name__ == "__main__":
    main()
