"""Load and validate the German to English glossary."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


class GlossaryError(Exception):
    """The glossary file is missing or malformed."""


@dataclass(frozen=True)
class Pattern:
    matcher: re.Pattern[str]
    replacement: str


@dataclass(frozen=True)
class Glossary:
    columns: dict[str, str]
    passthrough_columns: frozenset[str]
    no_number_localisation_columns: frozenset[str]
    patterns: tuple[Pattern, ...]
    terms: dict[str, str]


def load_glossary(path: Path) -> Glossary:
    """Read ``path`` and compile its patterns, or raise :class:`GlossaryError`."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GlossaryError(f"glossary not found at {path}") from error
    except json.JSONDecodeError as error:
        raise GlossaryError(f"{path.name}: invalid JSON - {error}") from error

    patterns: list[Pattern] = []
    for entry in raw.get("patterns", []):
        if "de" not in entry or "en" not in entry:
            raise GlossaryError(f"{path.name}: every pattern needs both 'de' and 'en': {entry!r}")
        try:
            matcher = re.compile(entry["de"])
        except re.error as error:
            raise GlossaryError(f"{path.name}: invalid regex {entry['de']!r} - {error}") from error
        patterns.append(Pattern(matcher=matcher, replacement=entry["en"]))

    return Glossary(
        columns=raw.get("columns", {}),
        passthrough_columns=frozenset(raw.get("passthrough_columns", ())),
        no_number_localisation_columns=frozenset(raw.get("no_number_localisation_columns", ())),
        patterns=tuple(patterns),
        terms=raw.get("terms", {}),
    )
