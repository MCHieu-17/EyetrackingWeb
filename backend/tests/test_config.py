import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings


def test_db_pool_settings_are_consistent():
    assert settings.db_pool_min >= 1
    assert settings.db_pool_max >= settings.db_pool_min


def test_worker_poll_seconds_positive():
    assert settings.worker_poll_seconds > 0


def test_gaze_fps_in_valid_range():
    assert 1 <= settings.gaze_fps <= 60


def test_gaze_max_gap_follows_fps():
    assert Settings(gaze_fps=12).gaze_max_gap_ms == 250
    assert Settings(gaze_fps=15).gaze_max_gap_ms == 250
    assert Settings(gaze_fps=6).gaze_max_gap_ms == 500
    assert Settings(gaze_fps=4).gaze_max_gap_ms == 750


@pytest.mark.parametrize("fps", [0, 61])
def test_gaze_fps_rejects_out_of_range(fps):
    with pytest.raises(ValidationError):
        Settings(gaze_fps=fps)
