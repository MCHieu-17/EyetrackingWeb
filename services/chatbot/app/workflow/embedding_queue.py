"""One model worker for chat and ingest; bounded priority queue and query-only LRU."""

import asyncio
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from itertools import count
from queue import Empty, PriorityQueue

from langchain_core.embeddings import Embeddings

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
    def __init__(self, model, model_key):
        self.model = model
        self.model_key = model_key
        self.queue = PriorityQueue()
        self.capacity = threading.BoundedSemaphore(512)
        self.sequence = count()
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.worker = threading.Thread(target=self._run, daemon=True, name="embedding-model")
        self.worker.start()

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
        self.queue.put_nowait(
            (0 if query else 1, next(self.sequence), Job(text, query, future, time.monotonic()))
        )
        return future

    def _run(self):
        import logging

        logger = logging.getLogger(__name__)
        while not self.stopping.is_set():
            try:
                priority, sequence, first = self.queue.get(timeout=0.1)
            except Empty:
                continue
            jobs = [first]
            end = time.monotonic() + 0.010
            while len(jobs) < 8 and time.monotonic() < end:
                try:
                    item = self.queue.get(timeout=max(0.0001, end - time.monotonic()))
                except Empty:
                    break
                if item[2].query != first.query:
                    self.queue.put_nowait(item)
                    break
                jobs.append(item[2])
            # A chat request arriving during ingest collection takes precedence.
            with self.queue.mutex:
                chat_waiting = bool(self.queue.queue and self.queue.queue[0][0] == 0)
            if not first.query and chat_waiting:
                for job in jobs:
                    self.queue.put_nowait((1, next(self.sequence), job))
                continue
            jobs = [j for j in jobs if not j.future.cancelled()]
            if not jobs:
                continue
            try:
                texts = [j.text for j in jobs]
                if first.query and hasattr(self.model, "_embed"):
                    vectors = self.model._embed(texts, self.model.query_encode_kwargs)
                elif first.query:
                    vectors = [self.model.embed_query(t) for t in texts]
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
                result.extend(f.result(timeout=60) for f in futures)
            except BaseException:
                for f in futures:
                    f.cancel()
                raise
        return result

    def close(self):
        self.stopping.set()
        while True:
            try:
                _, _, job = self.queue.get_nowait()
                job.future.cancel()
            except Empty:
                break
        self.worker.join(timeout=5)
