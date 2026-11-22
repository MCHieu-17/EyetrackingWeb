"""One shared embedding model with separate query and ingest lanes.

Query và ingest dùng chung weights để chỉ có một instance model, nhưng mỗi lane
có worker riêng nên query không phải xếp sau batch ingest. Cache query dùng
chung và vẫn giữ TTL/LRU như trước.
"""

import asyncio
import logging
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Empty, Queue

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

INSTRUCTION = (
    "Instruct: Retrieve relevant educational documents for answering student questions.\nQuery: "
)


@dataclass
class Job:
    text: str
    query: bool
    future: Future
    queued: float


class ManagedEmbedding(Embeddings):
    QUERY_BATCH = 4
    INGEST_BATCH = 8
    INGEST_BATCH_WHEN_QUERY = 2

    def __init__(self, model, model_key):
        self.model = model
        self.model_key = model_key
        self.query_queue = Queue()
        self.ingest_queue = Queue()
        self.capacity = threading.BoundedSemaphore(512)
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.query_worker = threading.Thread(
            target=self._run_query, daemon=True, name="embedding-query"
        )
        self.ingest_worker = threading.Thread(
            target=self._run_ingest, daemon=True, name="embedding-ingest"
        )
        self.query_worker.start()
        self.ingest_worker.start()
        logger.info(
            "embedding_model_instance key=%s pid=%s", model_key, os.getpid()
        )

    def _submit(self, text, query):
        future = Future()
        if self.stopping.is_set():
            raise RuntimeError("Embedding worker closed")
        if query:
            key = (text, self.model_key, INSTRUCTION)
            with self.lock:
                cached = self.cache.get(key)
                if cached and time.monotonic() - cached[0] < 900:
                    self.cache.move_to_end(key)
                    future.set_result(list(cached[1]))
                    return future
                self.cache.pop(key, None)
        if not self.capacity.acquire(blocking=False):
            raise RuntimeError("Embedding queue overloaded")
        future.add_done_callback(lambda _: self.capacity.release())
        queue = self.query_queue if query else self.ingest_queue
        queue.put_nowait(Job(text, query, future, time.monotonic()))
        return future

    def _collect(self, queue: Queue, first: Job, limit: int) -> list[Job]:
        jobs = [first]
        end = time.monotonic() + 0.010
        while len(jobs) < limit:
            try:
                jobs.append(queue.get(timeout=max(0.0001, end - time.monotonic())))
            except Empty:
                break
        return jobs

    def _encode(self, jobs: list[Job]) -> None:
        jobs = [job for job in jobs if not job.future.cancelled()]
        if not jobs:
            return
        try:
            texts = [job.text for job in jobs]
            if jobs[0].query and hasattr(self.model, "_embed"):
                vectors = self.model._embed(texts, self.model.query_encode_kwargs)
            elif jobs[0].query:
                vectors = [self.model.embed_query(text) for text in texts]
            else:
                vectors = self.model.embed_documents(texts)
            for job, vector in zip(jobs, vectors, strict=True):
                if job.future.cancelled():
                    continue
                if job.query:
                    with self.lock:
                        self.cache[(job.text, self.model_key, INSTRUCTION)] = (
                            time.monotonic(),
                            list(vector),
                        )
                        while len(self.cache) > 1024:
                            self.cache.popitem(last=False)
                logger.info(
                    "embedding queue_seconds=%.3f query=%s batch=%s",
                    time.monotonic() - job.queued,
                    job.query,
                    len(jobs),
                )
                job.future.set_result(vector)
        except Exception as exc:
            for job in jobs:
                if not job.future.done():
                    job.future.set_exception(exc)

    def _run_query(self) -> None:
        while not self.stopping.is_set():
            try:
                first = self.query_queue.get(timeout=0.1)
            except Empty:
                continue
            self._encode(self._collect(self.query_queue, first, self.QUERY_BATCH))

    def _run_ingest(self) -> None:
        while not self.stopping.is_set():
            try:
                first = self.ingest_queue.get(timeout=0.1)
            except Empty:
                continue
            limit = (
                self.INGEST_BATCH_WHEN_QUERY
                if not self.query_queue.empty()
                else self.INGEST_BATCH
            )
            self._encode(self._collect(self.ingest_queue, first, limit))

    def embed_query(self, text):
        future = self._submit(text, True)
        try:
            return future.result(timeout=60)
        except BaseException:
            future.cancel()
            raise

    async def aembed_query(self, text):
        future = self._submit(text, True)
        try:
            async with asyncio.timeout(60):
                return await asyncio.wrap_future(future)
        except BaseException:
            future.cancel()
            raise

    def embed_documents(self, texts):
        # Submit bounded batches; ingestion cannot fill the entire queue.
        result = []
        for start in range(0, len(texts), 8):
            futures = [self._submit(t, False) for t in texts[start : start + 8]]
            try:
                # Ingest chạy nền, có thể xếp hàng sau nhiều slide khác; 60s
                # trước đây làm rớt oan các slide cuối. 180s đủ rộng cho batch
                # 8 slide trong khi chat vẫn được ưu tiên.
                result.extend(f.result(timeout=180) for f in futures)
            except BaseException:
                for f in futures:
                    f.cancel()
                raise
        return result

    def close(self):
        self.stopping.set()
        for queue in (self.query_queue, self.ingest_queue):
            while True:
                try:
                    job = queue.get_nowait()
                except Empty:
                    break
                job.future.cancel()
        self.query_worker.join(timeout=5)
        self.ingest_worker.join(timeout=5)
