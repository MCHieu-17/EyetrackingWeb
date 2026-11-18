"""Tests cho vòng đời session calibration trong RAM."""

from app.services import sessions as sessions_module
from app.services.sessions import Session, SessionManager, SessionState
from app.settings import Settings


def make_settings(**overrides) -> Settings:
    values = {
        "device": "cpu",
        "unigaze_model": "unigaze_b16_joint",
        "session_ttl_seconds": 60,
        "max_sessions": 2,
    }
    values.update(overrides)
    return Settings(**values)


def test_session_create_get_delete_and_limit():
    manager = SessionManager(make_settings(max_sessions=1))
    sid = manager.create({"p": (0.5, 0.5)})
    assert manager.get(sid) is not None
    assert manager.count() == 1
    try:
        manager.create({"p": (0.5, 0.5)})
    except RuntimeError as exc:
        assert str(exc) == "too many sessions"
    else:
        raise AssertionError("expected session limit error")
    assert manager.delete(sid) is not None
    assert manager.get(sid) is None


def test_session_ttl_cleanup(monkeypatch):
    now = [1_000.0]
    monkeypatch.setattr(sessions_module.time, "monotonic", lambda: now[0])
    manager = SessionManager(make_settings(session_ttl_seconds=10))
    old_sid = manager.create({"p": (0.5, 0.5)})
    now[0] += 11
    new_sid = manager.create({"p": (0.5, 0.5)})
    assert manager.get(old_sid) is None
    assert manager.get(new_sid) is not None


def test_samples_keep_only_latest_per_point():
    session = Session(
        {"p": (0.5, 0.5)}, make_settings(max_samples_per_point=2)
    )
    for value in range(3):
        count = session.add_sample("p", float(value), 0.0)
    assert count == 2
    assert session.samples["p"] == [[1.0, 0.0, 0.5, 0.5], [2.0, 0.0, 0.5, 0.5]]


def test_mark_ready_resets_smoother_and_state():
    session = Session({"p": (0.5, 0.5)}, make_settings())
    assert session.state is SessionState.COLLECTING
    session.smoother.process([0.2, 0.2], timestamp=1.0)
    session.mark_ready()
    assert session.state is SessionState.READY
    assert session.ready is True
    assert session.smoother.x_prev is None


def test_manager_stats_counts_ready_sessions():
    manager = SessionManager(make_settings())
    first = manager.create({"p": (0.5, 0.5)})
    manager.create({"p": (0.5, 0.5)})
    manager.get(first).mark_ready()
    assert manager.stats() == {"total": 2, "ready": 1}
