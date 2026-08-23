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
    token = parse_first_token(raw_response)
    if token == first.casefold():
        return "first"
    if token == second.casefold():
        return "second"
    return "OTHER"


def exact_protocol_following(raw_response: str | None, first: str, second: str) -> bool:
    if raw_response is None:
        return False
    return raw_response.strip().casefold() in {first.casefold(), second.casefold()}


def external_routing_adherence(parsed_choice: str, frozen_assignment: str | None) -> bool | None:
    if frozen_assignment is None:
        return None
    if frozen_assignment not in {"first", "second"}:
        raise ValueError(f"invalid frozen external assignment: {frozen_assignment!r}")
    return parsed_choice == frozen_assignment
