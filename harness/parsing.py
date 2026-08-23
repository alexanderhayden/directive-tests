"""Small, explicit parsers for directive-test outputs."""

from __future__ import annotations

import re
import string

_PREFIX = re.compile(r"(?i)^(?:my )?answer(?: is)?\s*:\s*")
_TOKEN = re.compile(r"[^\s" + re.escape(string.punctuation) + r"]+")


def parse_first_token(raw_response: str | None) -> str | None:
    if raw_response is None:
        return None
    text = _PREFIX.sub("", raw_response.lstrip())
    match = _TOKEN.search(text)
    return match.group(0).casefold() if match else ""


def parse_candidate(raw_response: str | None, first: str, second: str) -> str:
    """Loose first-token classification retained only for diagnostics."""
    token = parse_first_token(raw_response)
    if token == first.casefold():
        return "first"
    if token == second.casefold():
        return "second"
    return "OTHER"


def strict_candidate_classification(
    raw_response: str | None,
    first: str,
    second: str,
) -> str:
    """Classify the complete trimmed response for the v2 primary outcome."""
    if raw_response is None:
        return "PROTOCOL_FAILURE"
    response = raw_response.strip().casefold()
    if response == first.casefold():
        return "first"
    if response == second.casefold():
        return "second"
    return "PROTOCOL_FAILURE"


def exact_protocol_following(raw_response: str | None, first: str, second: str) -> bool:
    if raw_response is None:
        return False
    return raw_response.strip().casefold() in {first.casefold(), second.casefold()}


def external_routing_adherence(parsed_choice: str, frozen_assignment: str | None) -> bool | None:
    """Loose first-token routing diagnostic retained for v2 description only."""
    if frozen_assignment is None:
        return None
    if frozen_assignment not in {"first", "second"}:
        raise ValueError(f"invalid frozen external assignment: {frozen_assignment!r}")
    return parsed_choice == frozen_assignment


def strict_external_routing_adherence(
    raw_response: str | None,
    first: str,
    second: str,
    frozen_assignment: str | None,
) -> bool | None:
    """Require the complete trimmed response to equal the frozen candidate."""
    if frozen_assignment is None:
        return None
    if frozen_assignment not in {"first", "second"}:
        raise ValueError(f"invalid frozen external assignment: {frozen_assignment!r}")
    if raw_response is None:
        return False
    assigned_candidate = first if frozen_assignment == "first" else second
    return raw_response.strip().casefold() == assigned_candidate.casefold()
