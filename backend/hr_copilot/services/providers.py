"""Local-only LLM runtime providers for the HR Copilot."""

import json
import logging
import os
import re
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3-8b-q4km-local"


class LLMProviderError(Exception):
    """A local LLM runtime could not complete a request."""


class LLMProviderConfigurationError(LLMProviderError):
    """The provider configuration is invalid or is not local-only."""


@dataclass(frozen=True)
class ProviderHealth:
    configured: bool
    available: bool
    provider: str | None
    model: str | None
    detail: str | None = None

    def as_dict(self):
        return {
            "configured": self.configured,
            "available": self.available,
            "provider": self.provider,
            "model": self.model,
            "detail": self.detail,
        }


class LocalOllamaQwenProvider:
    """Calls a locally running Ollama instance hosting Qwen3-8B."""

    provider_name = "local_ollama_qwen"

    def __init__(self, base_url=None, model=None, timeout_seconds=None, temperature=None):
        configured_url = (base_url or os.environ.get("HR_COPILOT_LLM_URL") or DEFAULT_OLLAMA_URL).rstrip("/")
        self.base_url = self._normalise_base_url(configured_url)
        self.model = model or os.environ.get("HR_COPILOT_LLM_MODEL") or DEFAULT_MODEL
        self.timeout_seconds = int(timeout_seconds or os.environ.get("HR_COPILOT_LLM_TIMEOUT_SECONDS", "30"))
        self.temperature = float(temperature if temperature is not None else os.environ.get("HR_COPILOT_LLM_TEMPERATURE", "0"))
        self._validate_configuration()

    def _validate_configuration(self):
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in LOCAL_HOSTS or parsed.username or parsed.password:
            raise LLMProviderConfigurationError("The HR Copilot LLM provider must use a local Ollama HTTP endpoint.")
        if not self.model or len(self.model) > 200:
            raise LLMProviderConfigurationError("A local Ollama model name is required.")
        if not 1 <= self.timeout_seconds <= 900:
            raise LLMProviderConfigurationError("The local LLM timeout must be between 1 and 900 seconds.")

    @staticmethod
    def _normalise_base_url(value):
        parsed = urlparse(value)
        if parsed.path in {"/api/chat", "/api/generate", "/api/tags"}:
            return value.rsplit("/api/", 1)[0]
        return value

    def _request(self, path, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, ValueError, OSError) as error:
            logger.warning("Local Ollama request failed: %s", error)
            raise LLMProviderError("The local Qwen model is unavailable.") from error

    def generate(self, prompt, *, options=None):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A prompt is required.")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature, **(options or {})},
        }
        result = self._request("/api/generate", payload)
        if not isinstance(result.get("response"), str):
            raise LLMProviderError("The local Qwen model returned an invalid response.")
        return result["response"]

    def chat(self, messages, *, response_format=None, options=None, think=None):
        if not isinstance(messages, list) or not messages:
            raise ValueError("At least one chat message is required.")
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, **(options or {})},
        }
        if response_format:
            payload["format"] = response_format
        # Always disable thinking for HR Copilot to prevent exposure to users
        payload["think"] = False
        result = self._request("/api/chat", payload)
        content = result.get("message", {}).get("content")
        if not isinstance(content, str):
            raise LLMProviderError("The local Qwen model returned an invalid response.")
        # Remove any thinking tags that might still appear
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content

    def structured_output(self, messages, *, schema="json", options=None):
        content = self.chat(messages, response_format=schema, options=options)
        try:
            result = json.loads(content)
        except (TypeError, ValueError) as error:
            raise LLMProviderError("The local Qwen model returned invalid structured output.") from error
        if not isinstance(result, dict):
            raise LLMProviderError("The local Qwen model returned invalid structured output.")
        return result

    def health(self):
        try:
            models = self._request("/api/tags").get("models", [])
        except LLMProviderError:
            return ProviderHealth(True, False, self.provider_name, self.model, "Local Ollama is unavailable.")
        names = {entry.get("name", "").split(":", 1)[0] for entry in models if isinstance(entry, dict)}
        if self.model.split(":", 1)[0] not in names:
            return ProviderHealth(True, False, self.provider_name, self.model, "The configured local Qwen model is not installed.")
        return ProviderHealth(True, True, self.provider_name, self.model)


def get_llm_provider():
    configured_provider = os.environ.get("HR_COPILOT_LLM_PROVIDER", "").strip().casefold()
    legacy_url = os.environ.get("HR_COPILOT_LLM_URL", "").strip()
    if configured_provider in {"", "disabled"} and not legacy_url:
        return None
    if configured_provider and configured_provider not in {"local_ollama_qwen", "ollama"}:
        raise LLMProviderConfigurationError("Only the local Ollama Qwen provider is supported.")
    return LocalOllamaQwenProvider(base_url=legacy_url or None)


def provider_health():
    try:
        provider = get_llm_provider()
    except LLMProviderConfigurationError:
        return ProviderHealth(True, False, "local_ollama_qwen", None, "The local LLM configuration is invalid.")
    if provider is None:
        return ProviderHealth(False, False, None, None, "The local LLM provider is not configured.")
    return provider.health()
