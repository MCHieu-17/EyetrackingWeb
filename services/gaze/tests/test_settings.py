"""Settings: đọc env một chỗ, validate fail-fast."""

from pathlib import Path

import pytest

from app.settings import Settings, frame_interval_ms


def make(**overrides) -> Settings:
    values = {
        "device": "cpu",
        "unigaze_model": "unigaze_b16_joint",
        "weights_dir": Path("/tmp/weights"),
    }
    values.update(overrides)
    return Settings(**values)


def test_validate_accepts_explicit_cpu_config():
    make().validate()


@pytest.mark.parametrize("device", ["", "gpu", "mps"])
def test_validate_rejects_invalid_device(device):
    with pytest.raises(RuntimeError, match="DEVICE"):
        make(device=device).validate()


@pytest.mark.parametrize("precision", ["", "bf16", "int8"])
def test_validate_rejects_invalid_precision(precision):
    with pytest.raises(RuntimeError, match="INFERENCE_PRECISION"):
        make(precision=precision).validate()


def test_validate_rejects_fp16_on_cpu():
    with pytest.raises(RuntimeError, match="fp16"):
        make(precision="fp16", device="cpu").validate()


def test_validate_accepts_fp16_on_cuda():
    make(precision="fp16", device="cuda").validate()


@pytest.mark.parametrize("model", ["", "../model", "a/b", ".hidden"])
def test_validate_rejects_invalid_model_name(model):
    with pytest.raises(RuntimeError, match="UNIGAZE_MODEL"):
        make(unigaze_model=model).validate()


@pytest.mark.parametrize("fps", [0, 61])
def test_validate_rejects_fps_out_of_range(fps):
    with pytest.raises(ValueError, match="1..60"):
        make(gaze_fps=fps).validate()


def test_frame_interval_ms_from_fps():
    assert frame_interval_ms(12) == 70
    assert frame_interval_ms(15) == 56
    assert frame_interval_ms(1) == 850
    assert frame_interval_ms(60) == 14


def test_from_env_reads_explicit_values(monkeypatch):
    monkeypatch.setenv("DEVICE", "cuda")
    monkeypatch.setenv("UNIGAZE_MODEL", "unigaze_l16_joint")
    monkeypatch.setenv("INFERENCE_PRECISION", "fp16")
    monkeypatch.setenv("GAZE_FPS", "10")
    monkeypatch.setenv("MAX_QUEUE", "4")
    monkeypatch.setenv("FRAME_MAX_AGE_MS", "150")
    monkeypatch.setenv("WEIGHTS_DIR", "/tmp/w")

    parsed = Settings.from_env()
    assert parsed.device == "cuda"
    assert parsed.unigaze_model == "unigaze_l16_joint"
    assert parsed.precision == "fp16"
    assert parsed.gaze_fps == 10
    assert parsed.max_queue == 4
    assert parsed.frame_max_age_ms == 150
    assert parsed.weights_dir == Path("/tmp/w")
    assert parsed.min_frame_interval_s == pytest.approx(0.085)
    assert parsed.unigaze_weights_path() == Path(
        "/tmp/w/unigaze_l16_joint.safetensors"
    )
