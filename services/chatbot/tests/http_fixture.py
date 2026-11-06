"""Real HTTP/pgvector fixture; only VLM/embedding/LLM providers are deterministic."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


class Embedding:
    def embed_documents(self, texts):
        return [[1.0] + [0.0] * 1023 for _ in texts]

    async def aembed_query(self, text):
        return self.embed_query(text)

    def close(self):
        pass

    def embed_query(self, text):
        return [1.0] + [0.0] * 1023


class Model(RunnableLambda):
    def __init__(self):
        super().__init__(lambda _: AIMessage(content="Khóa chính xác định duy nhất mỗi hàng [1]."))

    def with_structured_output(self, schema, **kwargs):
        def result(_):
            if schema.__name__ == "VLMOutput":
                return schema(transcript="Khóa chính xác định duy nhất mỗi hàng.")
            if schema.__name__ == "LeakageCheck":
                return schema(safe=True, inferred_options=[], reason="fixture")
            if schema.__name__ == "RouterOutput":
                return schema(intent="course_qa")
            return schema(
                claims=[
                    {
                        "claim": "Khóa chính xác định duy nhất mỗi hàng",
                        "claim_type": "course",
                        "citation_ids": [1],
                        "supported": True,
                        "evidence_quote": "Khóa chính xác định duy nhất mỗi hàng.",
                    }
                ]
            )

        return RunnableLambda(result)


from app.workflow import providers

providers.get_embedding = lambda *a, **kw: Embedding()
providers.get_vlm = lambda *a, **kw: Model()
providers.get_llm = lambda *a, **kw: Model()

from app.main import app  # noqa: E402,F401
from app.workflow import lms, river


class RiverFixture:
    async def structured(self, purpose, prompt, schema):
        if schema.__name__ == "RoutePlan":
            return schema(routes=["knowledge"])
        return Model().with_structured_output(schema).invoke(prompt)

    async def stream(self, prompt):
        yield '{"markdown":"Khóa chính xác định duy nhất mỗi hàng [1]."}\n'

    async def close(self): pass

river.get_river = lambda: RiverFixture()

# Backend's real proxy checks access before every block and before saving. Its
# TestClient has no listening port for the reverse HTTP callback in this fixture.
async def access_fixture(state): pass
lms.check_access = access_fixture
