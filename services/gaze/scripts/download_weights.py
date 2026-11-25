"""Tải weights vào WEIGHTS_DIR cho service `gaze-export`.

- mặc định: chỉ FaceLandmarker (`face_landmarker.task`) — runtime gaze không cần
  safetensors vì landmarker và UniGaze đều chạy bằng ONNX;
- `--unigaze`: tải thêm safetensors của UNIGAZE_MODEL để export ONNX
  (xem scripts/export_onnx.py).

Chỉ `export-entrypoint.sh` gọi script này (runtime không tải weights); khi dev
có thể chạy trực tiếp `python scripts/download_weights.py`.
"""

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

# Cho phép chạy trực tiếp file script (khi đó sys.path[0] là scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import Settings  # noqa: E402

WEIGHTS_DIR = str(Settings.from_env().weights_dir)

LANDMARKER_FILE = {
    "name": "face_landmarker.task",
    "sources": [
        ("url", "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"),
    ],
    "min_size": 3_000_000,
    "sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
}

# Chỉ tải đúng model được chọn trong UNIGAZE_MODEL. Kích thước lấy từ
# Content-Length của HuggingFace; `min_size` chặn file tải dở.
_UNIGAZE_BASE_URL = (
    "https://huggingface.co/UniGaze/UniGaze-models/resolve/main"
)
KNOWN_UNIGAZE = {
    "unigaze_b16_joint": {
        "name": "unigaze_b16_joint.safetensors",
        "sources": [("url", f"{_UNIGAZE_BASE_URL}/unigaze_b16_joint.safetensors")],
        "min_size": 346_291_616,
        # Pin SHA256 để khởi động reproducible (file HF cố định theo revision).
        "sha256": "2580d707b1395840ecabe7906e2cb35705f38c4ddb0be9c3c38ebb2d5546ffb8",
    },
    "unigaze_l16_joint": {
        "name": "unigaze_l16_joint.safetensors",
        "sources": [("url", f"{_UNIGAZE_BASE_URL}/unigaze_l16_joint.safetensors")],
        "min_size": 1_217_344_208,
    },
    "unigaze_h14_joint": {
        "name": "unigaze_h14_joint.safetensors",
        "sources": [("url", f"{_UNIGAZE_BASE_URL}/unigaze_h14_joint.safetensors")],
        "min_size": 2_528_232_848,
    },
    "unigaze_h14_cross_X": {
        "name": "unigaze_h14_cross_X.safetensors",
        "sources": [
            ("url", f"{_UNIGAZE_BASE_URL}/unigaze_h14_cross_X.safetensors")
        ],
        "min_size": 2_528_232_848,
    },
}

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


def _selected_model_file(settings: Settings):
    """Entry cần tải cho UNIGAZE_MODEL; None nếu file đã có sẵn."""
    model = settings.unigaze_model
    known = KNOWN_UNIGAZE.get(model)
    if known is not None:
        return known

    path = os.path.join(WEIGHTS_DIR, f"{model}.safetensors")
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        print(f"[weights] {model}: co san (khong co checksum)")
        return None
    raise RuntimeError(
        f"UNIGAZE_MODEL={model!r} chưa có cấu hình tải. "
        "Thêm entry vào KNOWN_UNIGAZE hoặc đặt file "
        f"{model}.safetensors vào volume gaze-weights."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unigaze", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    selected = None
    try:
        settings.validate()  # fail-fast nếu thiếu DEVICE/UNIGAZE_MODEL
        if args.unigaze:
            selected = _selected_model_file(settings)
    except (RuntimeError, ValueError) as exc:
        print(f"LOI: {exc}", file=sys.stderr)
        return 1

    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    files = [LANDMARKER_FILE]
    if selected is not None:
        files.append(selected)

    ok = True
    for f in files:
        ok = ensure(**f) and ok
    if not ok:
        print(
            "LOI: khong tai du weights. Kiem tra mang va URL nguon.",
            file=sys.stderr,
        )
        return 1
    print("[weights] Tat ca weights da san sang.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
