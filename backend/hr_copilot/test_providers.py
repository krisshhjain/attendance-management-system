import io
import json

from hr_copilot.services import providers


def response_for(content):
    return io.BytesIO(json.dumps(content).encode("utf-8"))


def test_local_provider_uses_configured_model_and_generation_options(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return response_for({"message": {"content": "{\"intent\": \"unknown\"}"}})

    monkeypatch.setattr(providers, "urlopen", fake_urlopen)
    provider = providers.LocalOllamaQwenProvider(
        base_url="http://127.0.0.1:11434/api/chat",
        model="qwen3-8b-q4km-local",
        timeout_seconds=45,
        temperature=0,
    )

    assert provider.structured_output([{"role": "user", "content": "hello"}]) == {"intent": "unknown"}
    request, timeout = calls[0]
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 45
    body = json.loads(request.data)
    assert body["model"] == "qwen3-8b-q4km-local"
    assert body["think"] is False


def test_health_requires_local_model_to_be_listed(monkeypatch):
    monkeypatch.setattr(providers, "urlopen", lambda *_args, **_kwargs: response_for({
        "models": [{"name": "qwen3-8b-q4km-local:latest"}],
    }))
    provider = providers.LocalOllamaQwenProvider(model="qwen3-8b-q4km-local")

    assert provider.health().as_dict() == {
        "configured": True,
        "available": True,
        "provider": "local_ollama_qwen",
        "model": "qwen3-8b-q4km-local",
        "detail": None,
    }


def test_cloud_provider_endpoints_are_not_allowed():
    try:
        providers.LocalOllamaQwenProvider(base_url="https://example.com")
    except providers.LLMProviderConfigurationError:
        pass
    else:
        raise AssertionError("A cloud endpoint must not be accepted.")
