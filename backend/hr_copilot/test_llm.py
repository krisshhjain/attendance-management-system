import io
import json
from urllib.error import URLError

import pytest

from hr_copilot.services import llm, providers
from hr_copilot.services.pipeline import CopilotError


def response_for(content):
    return io.BytesIO(json.dumps({"message": {"content": json.dumps(content)}}).encode())


def test_provider_is_optional_when_url_is_not_configured(monkeypatch):
    monkeypatch.delenv("HR_COPILOT_LLM_URL", raising=False)
    monkeypatch.delenv("HR_COPILOT_LLM_PROVIDER", raising=False)
    assert llm.get_structured_intent("How many employees in C1?") is None


def test_ollama_provider_sends_json_intent_request(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setenv("HR_COPILOT_LLM_PROVIDER", "local_ollama_qwen")
    monkeypatch.setenv("HR_COPILOT_LLM_MODEL", "qwen3-8b-q4km-local")
    monkeypatch.setenv("HR_COPILOT_LLM_TIMEOUT_SECONDS", "20")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return response_for({"intent": "employee_count", "source": "employee", "entities": {"section": "c"}})

    monkeypatch.setattr(providers, "urlopen", fake_urlopen)
    result = llm.get_structured_intent("How many employees in C?")
    assert result == {"intent": "employee_count", "source": "employee", "entities": {"section": "C"}}
    request, timeout = calls[0]
    body = json.loads(request.data)
    assert request.full_url == "http://localhost:11434/api/chat"
    assert body["model"] == "qwen3-8b-q4km-local"
    assert body["format"]["required"] == ["intent", "source", "entities"]
    assert timeout == 20
    assert "Never generate SQL" in body["messages"][0]["content"]


def test_provider_accepts_absence_intent_as_employee_query(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    yesterday = "2026-09-23"
    monkeypatch.setattr(providers, "urlopen", lambda *_args, **_kwargs: response_for({
        "intent": "absence_lookup",
        "source": "employee",
        "entities": {"date_range": {"start": yesterday, "end": yesterday}},
    }))

    assert llm.get_structured_intent("Who was absent yesterday?") == {
        "intent": "absence_lookup",
        "source": "employee",
        "entities": {"date_range": {"start": yesterday, "end": yesterday}},
    }


@pytest.mark.parametrize(
    "output",
    [
        {"intent": "drop_table", "source": "employee", "entities": {}},
        {"intent": "employee_count", "source": "attendance", "entities": {}},
        {"intent": "employee_count", "source": "employee", "entities": {"sql": "DROP TABLE"}},
        {"intent": "employee_count", "source": "employee", "entities": {"date_range": {"start": "yesterday"}}},
        {"intent": "employee_count", "source": "employee", "entities": {"employee_type": "CEO"}},
        {"intent": "employee_count", "source": "employee", "entities": {"comparison_subsections": [""]}},
        {"intent": "employee_count", "source": "employee", "entities": {"is_active": "yes"}},
    ],
)
def test_invalid_provider_output_is_rejected(monkeypatch, output):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(providers, "urlopen", lambda *_args, **_kwargs: response_for(output))
    with pytest.raises(CopilotError):
        llm.get_structured_intent("question")


def test_provider_network_failure_returns_controlled_error(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(providers, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")))
    with pytest.raises(CopilotError) as raised:
        llm.get_structured_intent("question")
    assert raised.value.code == "llm_unavailable"
    assert "offline" not in raised.value.message


def test_malformed_provider_json_is_rejected(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(providers, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"not-json"))
    with pytest.raises(CopilotError) as raised:
        llm.get_structured_intent("question")
    assert raised.value.code == "llm_unavailable"


def test_cloud_or_custom_provider_url_is_rejected(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "https://llm.example/custom/api/chat")
    with pytest.raises(CopilotError) as raised:
        llm.get_structured_intent("unrelated")
    assert raised.value.code == "llm_unavailable"
