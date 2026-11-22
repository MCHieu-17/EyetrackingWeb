"""Normalize tensor phải khớp công thức cũ (x/255 - mean)/std."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from app.services.pipeline import GpuStage, PreparedFace

pytestmark = pytest.mark.fast


def _stage(dtype: torch.dtype) -> GpuStage:
    stage = GpuStage.__new__(GpuStage)
    stage.device = torch.device("cpu")
    stage.is_cuda = False
    stage.dtype = dtype
    stage.batch_hint = 4
    stage._host_buf = None
    stage._mean = torch.tensor(
        [0.485, 0.456, 0.406], dtype=torch.float32
    ).view(1, 3, 1, 1)
    stage._std = torch.tensor(
        [0.229, 0.224, 0.225], dtype=torch.float32
    ).view(1, 3, 1, 1)
    stage._norm_mean = stage._mean * 255.0
    stage._norm_std = stage._std * 255.0
    return stage


def _faces() -> list[PreparedFace]:
    rng = np.random.default_rng(7)
    return [
        PreparedFace(rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)),
        PreparedFace(rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)),
    ]


@pytest.mark.parametrize("dtype", [torch.float32, torch.float16])
def test_fused_normalize_matches_reference(dtype):
    stage = _stage(dtype)
    faces = _faces()

    actual = stage._to_batch_tensor(faces)

    stacked = np.stack([item.rgb for item in faces])
    expected = torch.from_numpy(stacked).permute(0, 3, 1, 2).float()
    expected = (expected / 255.0 - stage._mean) / stage._std
    expected = expected.to(dtype)

    tolerance = 1e-6 if dtype == torch.float32 else 2e-3
    torch.testing.assert_close(actual, expected, atol=tolerance, rtol=1e-5)
