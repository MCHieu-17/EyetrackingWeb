from app.core.config import settings


def test_db_pool_settings_are_consistent():
    assert settings.db_pool_min >= 1
    assert settings.db_pool_max >= settings.db_pool_min


def test_worker_poll_seconds_positive():
    assert settings.worker_poll_seconds > 0
