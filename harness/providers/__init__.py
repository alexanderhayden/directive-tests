"""Provider-neutral result schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderResult:
    requested_model: str
    actual_model: str | None
    provider: str
    client: str
    raw_response: str | None
    finish_reason: str | None
    response_id: str | None
    usage: dict[str, Any] | None
    sent_parameters: dict[str, Any]
    attempts: int
    attempt_failures: list[dict[str, Any]] = field(default_factory=list)
    failure: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)
