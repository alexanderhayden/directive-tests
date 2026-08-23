"""Ollama transport refactored from Artifact 1's direct local client."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from harness.providers import ProviderResult
from harness.sampling import run_with_retries


_OPTION_NAMES = {
    "temperature": "temperature",
    "top_p": "top_p",
    "top_k": "top_k",
    "max_tokens": "num_predict",
    "repeat_penalty": "repeat_penalty",
    "presence_penalty": "presence_penalty",
    "frequency_penalty": "frequency_penalty",
    "stop": "stop",
    "seed": "seed",
}


def _json_request(url: str, *, method: str, body: dict | None, timeout: int) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _native_options(parameters: dict) -> dict:
    """Translate the frozen harness names into one shared Ollama options object."""
    return {
        target: parameters[source]
        for source, target in _OPTION_NAMES.items()
        if source in parameters and parameters[source] is not None
    }


def _native_usage(body: dict) -> dict:
    prompt_tokens = body.get("prompt_eval_count")
    completion_tokens = body.get("eval_count")
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": (
            prompt_tokens + completion_tokens
            if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int)
            else None
        ),
        "total_duration_ns": body.get("total_duration"),
        "load_duration_ns": body.get("load_duration"),
        "prompt_eval_duration_ns": body.get("prompt_eval_duration"),
        "eval_duration_ns": body.get("eval_duration"),
    }


class OllamaProvider:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_seconds: int = 600):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def list_models(self) -> list[dict[str, Any]]:
        return _json_request(
            f"{self.base_url}/api/tags", method="GET", body=None, timeout=30
        ).get("models", [])

    def sample(
        self,
        *,
        model: str,
        interface: str,
        payload: str | list[dict],
        parameters: dict,
        max_attempts: int,
    ) -> ProviderResult:
        options = _native_options(parameters)
        if interface == "completion":
            if not isinstance(payload, str):
                raise TypeError("native raw generation requires a string prompt")
            endpoint = "api/generate"
            request_body = {
                "model": model,
                "prompt": payload,
                "raw": True,
                "stream": False,
                "options": options,
            }
            client = "ollama_native_generate_raw"
        elif interface == "chat":
            if not isinstance(payload, list):
                raise TypeError("native chat requires a message list")
            endpoint = "api/chat"
            request_body = {
                "model": model,
                "messages": payload,
                "stream": False,
                "options": options,
            }
            client = "ollama_native_chat"
        else:
            raise ValueError(f"unsupported Ollama interface: {interface}")

        def operation() -> dict:
            return _json_request(
                f"{self.base_url}/{endpoint}",
                method="POST",
                body=request_body,
                timeout=self.timeout_seconds,
            )

        outcome = run_with_retries(
            operation,
            max_attempts=max_attempts,
            retryable=(HTTPError, URLError, TimeoutError, ValueError, KeyError, IndexError, json.JSONDecodeError),
        )
        if outcome.value is None:
            last = outcome.failures[-1] if outcome.failures else None
            return ProviderResult(
                requested_model=model,
                actual_model=None,
                provider="Ollama",
                client=client,
                raw_response=None,
                finish_reason=None,
                response_id=None,
                usage=None,
                sent_parameters=request_body,
                attempts=outcome.attempts,
                attempt_failures=outcome.failures,
                failure=(f"{last['error_type']}: {last['error']}" if last else "unknown failure"),
            )

        body = outcome.value
        raw_response = (
            body.get("response")
            if interface == "completion"
            else body.get("message", {}).get("content")
        )
        return ProviderResult(
            requested_model=model,
            actual_model=body.get("model", model),
            provider="Ollama",
            client=client,
            raw_response=raw_response,
            finish_reason=body.get("done_reason"),
            response_id=None,
            usage=_native_usage(body),
            sent_parameters=request_body,
            attempts=outcome.attempts,
            attempt_failures=outcome.failures,
            failure=None,
            provider_timestamp=body.get("created_at"),
        )
