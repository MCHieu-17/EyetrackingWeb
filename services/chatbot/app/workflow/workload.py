"""Cross-thread ingestion admission; active chat requests take priority."""

import os
import threading
import time
from contextlib import contextmanager

_condition = threading.Condition()
_active_chats = 0
_ingest = threading.Semaphore(int(os.getenv("VLM_INGEST_CONCURRENCY", "4")))


def chat_started():
    global _active_chats
    with _condition:
        _active_chats += 1


def chat_finished():
    global _active_chats
    with _condition:
        _active_chats -= 1
        _condition.notify_all()


@contextmanager
def ingest_slot():
    timeout = float(os.getenv("VLM_INGEST_QUEUE_TIMEOUT", "900"))
    end = time.monotonic() + timeout
    if not _ingest.acquire(timeout=timeout):
        raise TimeoutError("Ingest đang chờ dung lượng VLM; hãy thử lại sau.")
    try:
        with _condition:
            while _active_chats:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Ingest nhường tài nguyên cho chat; hãy thử lại sau.")
                _condition.wait(timeout=remaining)
        yield
    finally:
        _ingest.release()
