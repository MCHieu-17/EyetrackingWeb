import pytest

from app.workflow import workload


def test_ingestion_yields_to_chat_and_times_out_bounded(monkeypatch):
    monkeypatch.setenv('VLM_INGEST_QUEUE_TIMEOUT','0.01')
    workload.chat_started()
    try:
        with pytest.raises(TimeoutError,match='nhường'):
            with workload.ingest_slot():
                pytest.fail('ingest must not start while chat is active')
    finally:
        workload.chat_finished()
    with workload.ingest_slot():
        pass
