"""OpenRouter transport with returned provider/model capture."""

from __future__ import annotations

import requests

from harness.providers import ProviderResult
from harness.sampling import run_with_retries

URL = "https://openrouter.ai/api/v1/chat/completions"


def sample_chat(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    parameters: dict,
    max_attempts: int = 4,
) -> ProviderResult:
    sent = {"model": model, "messages": messages, **parameters}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def operation() -> dict:
        response = requests.post(URL, headers=headers, json=sent, timeout=60)
        response.raise_for_status()
        return response.json()

    outcome = run_with_retries(
        operation,
        max_attempts=max_attempts,
        retryable=(requests.RequestException, ValueError, KeyError, IndexError),
    )
    if outcome.value is None:
        last = outcome.failures[-1]
        return ProviderResult(
            model, None, "OpenRouter", "openrouter_chat", None, None, None, None,
            sent, outcome.attempts, outcome.failures,
            f"{last['error_type']}: {last['error']}",
        )
    body = outcome.value
    choice = body["choices"][0]
    return ProviderResult(
        requested_model=model,
        actual_model=body.get("model"),
        provider=body.get("provider", "OpenRouter"),
        client="openrouter_chat",
        raw_response=choice["message"].get("content"),
        finish_reason=choice.get("finish_reason"),
        response_id=body.get("id"),
        usage=body.get("usage"),
        sent_parameters=sent,
        attempts=outcome.attempts,
        attempt_failures=outcome.failures,
    )
