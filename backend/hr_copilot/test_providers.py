import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hr_copilot.services import providers


def response_for(content):
    return io.BytesIO(json.dumps(content).encode("utf-8"))


def test_local_provider_uses_configured_model_and_generation_options(
    monkeypatch,
):
    calls = []

    def fake_open(request, timeout):
        calls.append((request, timeout))
        return response_for({"message": {"content": '{"intent": "unknown"}'}})

    monkeypatch.setattr(providers, "_open_local_request", fake_open)
    provider = providers.LocalOllamaQwenProvider(
        base_url="http://127.0.0.1:11434/api/chat",
        model="qwen3-8b-q4km-local",
        timeout_seconds=45,
        temperature=0,
    )

    assert provider.structured_output(
        [{"role": "user", "content": "hello"}]
    ) == {"intent": "unknown"}
    request, timeout = calls[0]
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 45
    body = json.loads(request.data)
    assert body["model"] == "qwen3-8b-q4km-local"
    assert body["think"] is False


def test_health_requires_local_model_to_be_listed(monkeypatch):
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: response_for(
            {
                "models": [{"name": "qwen3-8b-q4km-local:latest"}],
            }
        ),
    )
    provider = providers.LocalOllamaQwenProvider(model="qwen3-8b-q4km-local")

    assert provider.health().as_dict() == {
        "configured": True,
        "available": True,
        "provider": "local_ollama_qwen",
        "model": "qwen3-8b-q4km-local",
        "detail": None,
    }


def test_health_reports_missing_model_without_claiming_provider_available(
    monkeypatch,
):
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: response_for(
            {"models": [{"name": "another-model:latest"}]}
        ),
    )
    provider = providers.LocalOllamaQwenProvider(model="qwen3-8b-q4km-local")

    health = provider.health()

    assert health.available is False
    assert health.detail == "The configured local Qwen model is not installed."


@pytest.mark.parametrize("content", ["not json", "[]"])
def test_structured_output_rejects_malformed_or_non_object_model_output(
    monkeypatch, content
):
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: response_for(
            {"message": {"content": content}}
        ),
    )
    provider = providers.LocalOllamaQwenProvider()

    with pytest.raises(providers.LLMProviderError, match="invalid structured output"):
        provider.structured_output([{"role": "user", "content": "question"}])


def test_cloud_provider_endpoints_are_not_allowed():
    try:
        providers.LocalOllamaQwenProvider(base_url="https://example.com")
    except providers.LLMProviderConfigurationError:
        pass
    else:
        raise AssertionError("A cloud endpoint must not be accepted.")


def test_local_provider_rejects_redirects_to_other_hosts():
    forwarded_requests = []

    class DestinationHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            forwarded_requests.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    destination = ThreadingHTTPServer(
        ("127.0.0.1", 0), DestinationHandler
    )
    destination_thread = threading.Thread(
        target=destination.serve_forever, daemon=True
    )
    destination_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(307)
            self.send_header("Location", self.server.destination_url)
            self.end_headers()

        def log_message(self, *_args):
            pass

    redirector = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    redirector.destination_url = (
        f"http://127.0.0.1:{destination.server_port}/receive"
    )
    redirect_thread = threading.Thread(
        target=redirector.serve_forever, daemon=True
    )
    redirect_thread.start()

    try:
        provider = providers.LocalOllamaQwenProvider(
            base_url=f"http://127.0.0.1:{redirector.server_port}",
            timeout_seconds=2,
        )
        with pytest.raises(providers.LLMProviderError):
            provider.generate("sensitive prompt")
    finally:
        redirector.shutdown()
        destination.shutdown()
        redirect_thread.join(timeout=2)
        destination_thread.join(timeout=2)
        redirector.server_close()
        destination.server_close()

    if forwarded_requests:
        pytest.fail("The redirected request reached the other host.")
