"""Export UniGaze (safetensors) -> ONNX fp32 + fp16 kèm manifest.

Chạy trong image target `export` (có torch + unigaze); runtime KHÔNG có torch:

    python -m scripts.export_onnx              # theo UNIGAZE_MODEL, WEIGHTS_DIR
    python -m scripts.export_onnx --force

Đầu ra trong WEIGHTS_DIR:

    <model>.fp32.onnx  <model>.fp32.onnx.json
    <model>.fp16.onnx  <model>.fp16.onnx.json

Graph: input `rgb` uint8 [N,224,224,3] (ROI RGB thô; chuẩn hoá ImageNet nằm
trong graph) -> `pred_gaze` [N,2] (pitch, yaw) fp32. Chỉ trục batch `N` động.
Bản fp16 dùng weights fp16, giữ IO và phần chuẩn hoá ảnh ở fp32.

Idempotent: manifest khớp sha256 của safetensors nguồn + phiên bản exporter thì
bỏ qua. Manifest cũng là thứ service kiểm tra lúc khởi động.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import Settings  # noqa: E402

EXPORT_SCHEMA = 2
OPSET = 17
ROI = 224
PRECISIONS = ("fp32", "fp16")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def onnx_path(weights_dir: Path, model: str, precision: str) -> Path:
    return weights_dir / f"{model}.{precision}.onnx"


def manifest_path(path: Path) -> Path:
    return path.with_name(path.name + ".json")


def manifest_ok(path: Path, source_sha: str) -> bool:
    manifest = manifest_path(path)
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


def build_torch_model(weights: Path, *, ort_friendly: bool = False):
    """Nạp UniGaze; `ort_friendly` đổi 2 chỗ chậm trên ORT mà không đổi toán học:
    patch-embed Conv -> reshape + MatMul, attention -> MultiHeadAttention của ORT.
    """
    import torch
    import unigaze.loader as loader

    if weights.stem not in loader.MODEL_INDEX:
        raise SystemExit(
            f"UNIGAZE_MODEL={weights.stem!r} không có trong "
            f"unigaze.loader.MODEL_INDEX: {sorted(loader.MODEL_INDEX)}"
        )
    model = loader.build_unigaze_model(weights.stem)
    model.load_unigaze_weights(str(weights))
    model.eval()
    if ort_friendly:
        _make_ort_friendly(model.vit)

    class Wrapper(torch.nn.Module):
        """uint8 NHWC RGB -> chuẩn hoá ImageNet (trong graph) -> pitch/yaw."""

        def __init__(self, inner):
            super().__init__()
            self.inner = inner
            mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1) * 255.0
            std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1) * 255.0
            self.register_buffer("mean", mean)
            self.register_buffer("std", std)

        def forward(self, rgb):
            x = rgb.permute(0, 3, 1, 2).to(torch.float32)
            x = (x - self.mean) / self.std
            return self.inner(x)["pred_gaze"]

    return Wrapper(model).eval()


def _make_ort_friendly(vit) -> None:
    import torch
    from torch import nn

    class PatchProj(nn.Module):
        def __init__(self, conv):
            super().__init__()
            self.patch = conv.kernel_size[0]
            self.out = conv.out_channels
            self.w = nn.Parameter(
                conv.weight.detach().reshape(conv.out_channels, -1).t().contiguous()
            )
            self.b = nn.Parameter(conv.bias.detach())

        def forward(self, x):
            n, c, h, w = x.shape
            p = self.patch
            x = x.reshape(n, c, h // p, p, w // p, p)
            x = x.permute(0, 2, 4, 1, 3, 5).reshape(n, (h // p) * (w // p), -1)
            x = x @ self.w + self.b
            return x.transpose(1, 2).reshape(n, self.out, h // p, w // p)

    class OrtMHA(torch.autograd.Function):
        @staticmethod
        def forward(ctx, q, k, v, heads):
            b, s, c = q.shape
            q, k, v = (
                t.reshape(b, s, heads, c // heads).transpose(1, 2) for t in (q, k, v)
            )
            out = torch.nn.functional.scaled_dot_product_attention(q, k, v)
            return out.transpose(1, 2).reshape(b, s, c)

        @staticmethod
        def symbolic(g, q, k, v, heads):
            return g.op("com.microsoft::MultiHeadAttention", q, k, v, num_heads_i=heads)

    class Attn(nn.Module):
        def __init__(self, attn):
            super().__init__()
            self.qkv, self.proj, self.heads = attn.qkv, attn.proj, attn.num_heads

        def forward(self, x):
            q, k, v = self.qkv(x).chunk(3, dim=-1)
            out = OrtMHA.apply(q.contiguous(), k.contiguous(), v.contiguous(), self.heads)
            return self.proj(out)

    vit.patch_embed.proj = PatchProj(vit.patch_embed.proj)
    for block in vit.blocks:
        block.attn = Attn(block.attn)


def export_fp32(model, out: Path) -> None:
    import torch

    dummy = torch.randint(0, 256, (2, ROI, ROI, 3), dtype=torch.uint8)
    with torch.inference_mode():
        torch.onnx.export(
            model,
            dummy,
            str(out),
            input_names=["rgb"],
            output_names=["pred_gaze"],
            dynamic_axes={"rgb": {0: "N"}, "pred_gaze": {0: "N"}},
            opset_version=OPSET,
            do_constant_folding=True,
            dynamo=False,
            custom_opsets={"com.microsoft": 1},
        )


def optimize_fp32(src: Path, dst: Path, num_heads: int, hidden: int) -> None:
    """Gộp attention/LayerNorm/GELU bằng optimizer transformer của ORT."""
    from onnxruntime.transformers import optimizer

    opt = optimizer.optimize_model(
        str(src),
        model_type="vit",
        num_heads=num_heads,
        hidden_size=hidden,
        optimization_options=None,
        use_gpu=False,
    )
    opt.save_model_to_file(str(dst))


def to_fp16(src: Path, dst: Path) -> None:
    import onnx
    from onnxruntime.transformers import float16

    model = onnx.load(str(src))
    # Phần chuẩn hoá ảnh (trước MatMul đầu tiên) giữ fp32: giá trị 0..255 trong
    # fp16 chỉ còn bước 0.125 và làm lệch đầu vào của model.
    keep = []
    for node in model.graph.node:
        if node.op_type in ("MatMul", "Gemm", "Conv", "SkipLayerNormalization"):
            break
        keep.append(node.name)
    converted = float16.convert_float_to_float16(
        model, keep_io_types=True, disable_shape_infer=False, node_block_list=keep
    )
    onnx.save(converted, str(dst))


def write_manifest(
    path: Path, *, source_sha: str, model: str, precision: str
) -> None:
    import onnx
    import onnxruntime
    import torch

    data = {
        "export_schema": EXPORT_SCHEMA,
        "model": model,
        "precision": precision,
        "source_sha256": source_sha,
        "onnx_sha256": sha256_file(path),
        "opset": OPSET,
        "input": {"name": "rgb", "dtype": "uint8", "shape": ["N", ROI, ROI, 3]},
        "output": {"name": "pred_gaze", "dtype": "float32", "shape": ["N", 2]},
        "torch_version": torch.__version__,
        "onnx_version": onnx.__version__,
        "onnxruntime_version": onnxruntime.__version__,
    }
    manifest_path(path).write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def model_dims(model: str) -> tuple[int, int]:
    return {
        "vit_b_16": (12, 768),
        "vit_l_16": (16, 1024),
        "vit_h_14": (16, 1280),
    }[_model_type(model)]


def _model_type(model: str) -> str:
    import unigaze.loader as loader

    return loader.MODEL_INDEX[model]["model_kwargs"]["model_type"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--precisions", default=",".join(PRECISIONS), help="fp32,fp16"
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.unigaze_model:
        raise SystemExit("Thiếu UNIGAZE_MODEL.")
    weights = settings.unigaze_weights_path()
    if not weights.is_file():
        raise SystemExit(f"Không thấy safetensors tại {weights}.")

    wanted = [p.strip() for p in args.precisions.split(",") if p.strip()]
    source_sha = sha256_file(weights)
    targets = {p: onnx_path(settings.weights_dir, settings.unigaze_model, p) for p in wanted}
    if not args.force and all(manifest_ok(p, source_sha) for p in targets.values()):
        print("ONNX đã khớp safetensors nguồn; bỏ qua export.")
        return 0

    tmp_raw = settings.weights_dir / f"{settings.unigaze_model}.raw.onnx.tmp"
    tmp_opt = settings.weights_dir / f"{settings.unigaze_model}.opt.onnx.tmp"
    try:
        print(f"Export {weights.name} -> ONNX (opset {OPSET})")
        export_fp32(build_torch_model(weights, ort_friendly=True), tmp_raw)
        heads, hidden = model_dims(settings.unigaze_model)
        optimize_fp32(tmp_raw, tmp_opt, heads, hidden)

        for precision, target in targets.items():
            staging = target.with_suffix(".onnx.tmp")
            if precision == "fp32":
                staging.write_bytes(tmp_opt.read_bytes())
            else:
                to_fp16(tmp_opt, staging)
            staging.replace(target)
            write_manifest(
                target,
                source_sha=source_sha,
                model=settings.unigaze_model,
                precision=precision,
            )
            print(f"  ghi {target.name} ({target.stat().st_size / 1e6:.1f} MB)")
    finally:
        tmp_raw.unlink(missing_ok=True)
        tmp_opt.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
