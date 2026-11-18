"""Tests cho One-Euro smoothing."""

import pytest

from app.services import smoothing


def test_first_point_passes_through_unchanged():
    filt = smoothing.OneEuroFilter2D()
    assert filt.process([0.2, 0.8]) == [0.2, 0.8]


def test_filter_moves_toward_new_point_and_uses_velocity(monkeypatch):
    clock = iter([10.0, 10.1, 10.2])
    monkeypatch.setattr(smoothing.time, "monotonic", lambda: next(clock))
    filt = smoothing.OneEuroFilter2D(min_cutoff=0.5, beta=0.5, d_cutoff=1.0)

    filt.process([0.0, 0.0])
    first = filt.process([1.0, 0.0])
    second = filt.process([1.0, 0.0])

    assert 0.0 < first[0] < 1.0
    assert second[0] >= first[0]
    assert first[1] == pytest.approx(0.0)


def test_non_positive_dt_returns_previous_value(monkeypatch):
    clock = iter([10.0, 10.0])
    monkeypatch.setattr(smoothing.time, "monotonic", lambda: next(clock))
    filt = smoothing.OneEuroFilter2D()
    filt.process([0.2, 0.3])
    assert filt.process([0.9, 0.9]) == [0.2, 0.3]


def test_gap_longer_than_max_resets_to_new_point():
    filt = smoothing.OneEuroFilter2D()
    filt.process([0.2, 0.3], timestamp=10.0)
    assert filt.process([0.9, 0.9], timestamp=12.0) == [0.9, 0.9]


def test_explicit_timestamp_does_not_read_clock(monkeypatch):
    monkeypatch.setattr(
        smoothing.time,
        "monotonic",
        lambda: pytest.fail("không được đọc clock khi có timestamp"),
    )
    filt = smoothing.OneEuroFilter2D()
    assert filt.process([0.2, 0.3], timestamp=1.0) == [0.2, 0.3]
    assert filt.process([0.4, 0.3], timestamp=1.1)[0] > 0.2


def test_reset_without_coord_clears_state():
    filt = smoothing.OneEuroFilter2D()
    filt.process([0.2, 0.3], timestamp=1.0)
    filt.reset()
    assert filt.x_prev is None
    assert filt.t_prev is None
