from app.services.ingest import Ingestion, VLMOutput


def test_vlm_output_model():
    output = VLMOutput(transcript="# Slide")
    assert output.transcript == "# Slide"


def test_rate_limit_and_server_errors_are_retryable_vlm_failures():
    from types import SimpleNamespace

    import httpx
    import openai
    import pytest

    from app.services.ingest import VLMUnavailableError

    for code in (429, 503):
        response = httpx.Response(
            code, request=httpx.Request("POST", "https://provider.test/chat")
        )
        error = openai.APIStatusError("temporary", response=response, body={})

        def fail(_, exc=error):
            raise exc

        service = Ingestion.__new__(Ingestion)
        service.slide_to_text_chain = SimpleNamespace(invoke=fail)
        with pytest.raises(VLMUnavailableError):
            service._describe_image("image")


def test_partial_vlm_outage_returns_retryable_error():
    import pytest

    from app.services.ingest import VLMUnavailableError

    service = Ingestion.__new__(Ingestion)

    def embed(slide):
        if slide["slide_version_id"] == "bad":
            raise VLMUnavailableError("temporary")

    service._embed_slide = embed
    with pytest.raises(VLMUnavailableError):
        service._process_slides(
            [{"slide_version_id": "good"}, {"slide_version_id": "bad"}]
        )
