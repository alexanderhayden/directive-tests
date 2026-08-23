"""Direct OpenAI chat transport for future experiments."""

from __future__ import annotations

from harness.providers import ProviderResult
from harness.sampling import run_with_retries


def sample_chat(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    parameters: dict,
    max_attempts: int = 4,
) -> ProviderResult:
    import openai

    client = openai.OpenAI(api_key=api_key)
    sent = {"model": model, "messages": messages, **parameters}
    outcome = run_with_retries(
        lambda: client.chat.completions.create(**sent),
        max_attempts=max_attempts,
        retryable=(openai.APIError,),
    )
    if outcome.value is None:
        last = outcome.failures[-1]
        return ProviderResult(
            model, None, "OpenAI", "openai_chat", None, None, None, None,
            sent, outcome.attempts, outcome.failures,
            f"{last['error_type']}: {last['error']}",
        )
    response = outcome.value
    choice = response.choices[0]
    return ProviderResult(
        requested_model=model,
        actual_model=getattr(response, "model", None),
        provider="OpenAI",
        client="openai_chat",
        raw_response=choice.message.content,
        finish_reason=choice.finish_reason,
        response_id=response.id,
        usage=response.usage.model_dump() if response.usage else None,
        sent_parameters=sent,
        attempts=outcome.attempts,
        attempt_failures=outcome.failures,
    )
