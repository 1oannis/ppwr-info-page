"""Render a Declaration in English using the glossary.

Anything the glossary cannot resolve is collected as a failure and raised, so a
half-translated page can never reach the site. Failures are gathered across the
whole document before raising, so one build reports every missing term rather
than one per run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .glossary import Glossary
from .numbers import localise
from .workbook import Declaration

# {name} inserts a captured group; {name|term} resolves it through `terms`.
_GROUP_REFERENCE = re.compile(r"\{(?P<name>\w+)(?P<lookup>\|term)?\}")

_TITLE_FIELD = "title (cell A1)"
_LABEL_FIELD = "distributor label"


@dataclass(frozen=True)
class TranslationFailure:
    row: int  # 1-based data row; 0 for document-level fields
    column: str
    text: str

    def __str__(self) -> str:
        where = f"row {self.row}, {self.column}" if self.row else self.column
        return f"{where}: no translation for {self.text!r}"


class TranslationError(Exception):
    def __init__(self, failures: list[TranslationFailure]) -> None:
        self.failures = failures
        detail = "\n".join(f"  ERROR {failure}" for failure in failures)
        super().__init__(
            f"{len(failures)} untranslatable segment(s):\n{detail}\n"
            "  add them to data/glossary.json"
        )


class _Translator:
    def __init__(self, glossary: Glossary) -> None:
        self._glossary = glossary
        self._failures: list[TranslationFailure] = []

    def cell(self, text: str, column: str, row: int) -> str:
        if not text:
            return ""
        if column in self._glossary.passthrough_columns:
            return self._numbers(text, column)
        return self._numbers(self._translate(text, column, row), column)

    def column(self, german: str) -> str:
        english = self._glossary.columns.get(german)
        if english is None:
            self._failures.append(TranslationFailure(0, "column header", german))
            return german
        return english

    def raise_if_failed(self) -> None:
        if self._failures:
            raise TranslationError(self._failures)

    def _numbers(self, text: str, column: str) -> str:
        if column in self._glossary.no_number_localisation_columns:
            return text
        return localise(text)

    def _translate(self, text: str, column: str, row: int) -> str:
        # Patterns are tried on the intact cell first: German decimals use a
        # comma (e.g. "ca. 12,5 g pro Verpackung"), so splitting on commas
        # before matching would tear a number apart. Falls through to
        # comma-separated segments only when the whole cell doesn't match -
        # each pattern's capture groups are constrained (e.g. `[^,]+`, not
        # `.+`) so a whole-cell match never swallows a real list.
        whole = self._match(text, column, row)
        if whole is not None:
            return whole
        segments = [segment.strip() for segment in text.split(",")]
        return ", ".join(
            self._segment(segment, column, row) for segment in segments if segment
        )

    def _segment(self, segment: str, column: str, row: int) -> str:
        matched = self._match(segment, column, row)
        if matched is not None:
            return matched
        term = self._glossary.terms.get(segment)
        if term is not None:
            return term
        self._failures.append(TranslationFailure(row, column, segment))
        return segment

    def _match(self, text: str, column: str, row: int) -> str | None:
        for pattern in self._glossary.patterns:
            found = pattern.matcher.fullmatch(text)
            if found:
                return self._expand(pattern.replacement, found, column, row)
        return None

    def _expand(self, replacement: str, found: re.Match[str], column: str, row: int) -> str:
        def resolve(reference: re.Match[str]) -> str:
            value = found.group(reference.group("name"))
            if not reference.group("lookup"):
                return value
            term = self._glossary.terms.get(value)
            if term is None:
                self._failures.append(TranslationFailure(row, column, value))
                return value
            return term

        return _GROUP_REFERENCE.sub(resolve, replacement)


def translate(declaration: Declaration, glossary: Glossary) -> Declaration:
    """Return ``declaration`` rendered in English.

    Raises :class:`TranslationError` listing every segment the glossary could
    not resolve. Address lines are returned verbatim: an address is not
    translated.
    """
    translator = _Translator(glossary)

    columns = tuple(translator.column(column) for column in declaration.columns)
    rows = tuple(
        tuple(
            translator.cell(cell, column, number)
            for cell, column in zip(row, declaration.columns)
        )
        for number, row in enumerate(declaration.rows, start=1)
    )
    title = translator.cell(declaration.title, _TITLE_FIELD, 0)
    label = translator.cell(declaration.distributor_label, _LABEL_FIELD, 0)

    translator.raise_if_failed()

    return Declaration(
        title=title,
        distributor_label=label,
        distributor_lines=declaration.distributor_lines,
        columns=columns,
        rows=rows,
    )
