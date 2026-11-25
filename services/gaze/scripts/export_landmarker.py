"""Export FaceLandmarker (`face_landmarker.task`) -> hai ONNX fp32 + manifest.

Chạy ở image `export` (service `gaze-export`) sau `download_weights`. Runtime
chỉ cần các file ONNX, không cần mediapipe.

    <weights>/face_detector.onnx       + .json
    <weights>/face_landmarks.onnx      + .json

Idempotent: manifest khớp sha256 của `.task` + phiên bản exporter thì bỏ qua.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import Settings  # noqa: E402
from scripts.tflite_to_onnx import convert_file, extract_task  # noqa: E402

EXPORT_SCHEMA = 1
MODELS = {
    "face_detector.tflite": "face_detector",
    "face_landmarks_detector.tflite": "face_landmarks",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_ok(path: Path, source_sha: str) -> bool:
    manifest = path.with_name(path.name + ".json")
    if not path.is_file() or not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return (
        data.get("export_schema") == EXPORT_SCHEMA
        and data.get("source_sha256") == source_sha
        and data.get("onnx_sha256") == sha256_file(path)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    task = settings.face_landmarker_path()
    if not task.is_file():
        raise SystemExit(f"Không thấy FaceLandmarker task tại {task}.")
    source_sha = sha256_file(task)
    targets = {
        settings.face_detector_onnx_path(): "face_detector.tflite",
        settings.face_landmarks_onnx_path(): "face_landmarks_detector.tflite",
    }
    if not args.force and all(manifest_ok(p, source_sha) for p in targets):
        print("Landmarker ONNX đã khớp .task nguồn; bỏ qua export.")
        return 0

    import onnx

    with tempfile.TemporaryDirectory() as tmp:
        files = extract_task(task, Path(tmp))
        for target, member in targets.items():
            model = convert_file(files[member], MODELS[member])
            staging = target.with_suffix(".onnx.tmp")
            onnx.save(model, staging)
            staging.replace(target)
            target.with_name(target.name + ".json").write_text(
                json.dumps(
                    {
                        "export_schema": EXPORT_SCHEMA,
                        "source": member,
                        "source_sha256": source_sha,
                        "onnx_sha256": sha256_file(target),
                        "layout": "input NHWC float32, batch động",
                        "onnx_version": onnx.__version__,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"  ghi {target.name} ({target.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
