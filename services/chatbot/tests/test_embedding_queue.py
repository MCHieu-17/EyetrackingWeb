import concurrent.futures
from app.workflow.embedding_queue import ManagedEmbedding

class Model:
    def __init__(self): self.calls=[]
    def embed_query(self,text):
        self.calls.append(text)
        return [float(len(text))]
    def embed_documents(self,texts):
        self.calls.extend(texts)
        return [[float(len(t))] for t in texts]

def test_cache_only_queries_and_same_worker_for_ingest():
    model=Model()
    queue=ManagedEmbedding(model,'model')
    try:
        assert queue.embed_query('hello') == [5.0]
        assert queue.embed_query('hello') == [5.0]
        assert model.calls == ['hello']
        queue.embed_documents(['hello'])
        assert model.calls == ['hello','hello']
    finally: queue.close()

def test_concurrent_queries_and_ingestion_are_serialized():
    model=Model()
    queue=ManagedEmbedding(model,'model')
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
            futures=[pool.submit(queue.embed_query,str(i)) for i in range(30)]
            assert all(f.result(timeout=5) for f in futures)
        assert len(model.calls)==30
    finally: queue.close()
