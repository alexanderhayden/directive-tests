"""Direct Anthropic transport for future experiments."""

from __future__ import annotations

from harness.providers import ProviderResult
from harness.sampling import run_with_retries


def sample_messages(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    parameters: dict,
    max_attempts: int = 4,
) -> ProviderResult:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    sent = {"model": model, "messages": messages, **parameters}
    outcome = run_with_retries(
        lambda: client.messages.create(**sent),
        max_attempts=max_attempts,
        retryable=(anthropic.APIError,),
    )
    if outcome.value is None:
        last = outcome.failures[-1]
        return ProviderResult(
            model, None, "Anthropic", "anthropic_messages", None, None, None, None,
            sent, outcome.attempts, outcome.failures,
            f"{last['error_type']}: {last['error']}",
        )
    response = outcome.value
    text = "".join(block.text for block in response.content if block.type == "text")
    return ProviderResult(
        requested_model=model,
        actual_model=getattr(response, "model", None),
        provider="Anthropic",
        client="anthropic_messages",
        raw_response=text,
        finish_reason=response.stop_reason,
        response_id=response.id,
        usage=response.usage.model_dump() if response.usage else None,
        sent_parameters=sent,
        attempts=outcome.attempts,
        attempt_failures=outcome.failures,
    )
