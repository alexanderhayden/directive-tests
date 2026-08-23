"""Ollama transport refactored from Artifact 1's direct local client."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from harness.providers import ProviderResult
from harness.sampling import run_with_retries


def _json_request(url: str, *, method: str, body: dict | None, timeout: int) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


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
        if interface == "completion":
            endpoint = "completions"
            request_body = {"model": model, "prompt": payload, **parameters}
        elif interface == "chat":
            endpoint = "chat/completions"
            request_body = {"model": model, "messages": payload, **parameters}
        else:
            raise ValueError(f"unsupported Ollama interface: {interface}")

        def operation() -> dict:
            return _json_request(
                f"{self.base_url}/v1/{endpoint}",
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
                client=f"ollama_{interface}",
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
        choice = body["choices"][0]
        raw_response = (
            choice.get("text")
            if interface == "completion"
            else choice.get("message", {}).get("content")
        )
        return ProviderResult(
            requested_model=model,
            actual_model=body.get("model", model),
            provider="Ollama",
            client=f"ollama_{interface}",
            raw_response=raw_response,
            finish_reason=choice.get("finish_reason"),
            response_id=body.get("id"),
            usage=body.get("usage"),
            sent_parameters=request_body,
            attempts=outcome.attempts,
            attempt_failures=outcome.failures,
            failure=None,
        )
