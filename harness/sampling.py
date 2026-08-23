"""Bounded retry execution with retained attempt failures."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryOutcome(Generic[T]):
    value: T | None
    attempts: int
    failures: list[dict]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_with_retries(
    operation: Callable[[], T],
    *,
    max_attempts: int,
    retryable: tuple[type[BaseException], ...] = (Exception,),
    backoff_seconds: float = 1.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> RetryOutcome[T]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    failures: list[dict] = []
    for attempt in range(1, max_attempts + 1):
        try:
            return RetryOutcome(operation(), attempt, failures)
        except retryable as exc:
            failures.append(
                {
                    "attempt": attempt,
                    "utc_time": utc_now(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            if attempt < max_attempts:
                sleeper(backoff_seconds * (2 ** (attempt - 1)))
    return RetryOutcome(None, max_attempts, failures)
