"""Tests cho vòng đời session calibration trong RAM."""

from app.services import sessions as sessions_module


def test_session_create_get_delete_and_limit():
    manager = sessions_module.SessionManager(ttl=60, max_sessions=1)
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
    monkeypatch.setattr(sessions_module.time, "time", lambda: now[0])
    manager = sessions_module.SessionManager(ttl=10, max_sessions=2)
    old_sid = manager.create({"p": (0.5, 0.5)})
    now[0] += 11
    new_sid = manager.create({"p": (0.5, 0.5)})
    assert manager.get(old_sid) is None
    assert manager.get(new_sid) is not None


def test_samples_keep_only_latest_per_point(monkeypatch):
    monkeypatch.setattr(sessions_module, "MAX_SAMPLES_PER_POINT", 2)
    session = sessions_module.Session({"p": (0.5, 0.5)})
    for value in range(3):
        count = session.add_sample("p", float(value), 0.0)
    assert count == 2
    assert session.samples["p"] == [[1.0, 0.0, 0.5, 0.5], [2.0, 0.0, 0.5, 0.5]]
