"""Read the PPWR declaration spreadsheet into a plain data structure.

This module knows nothing about language or HTML. It locates the table by
searching for the header cell rather than by row number, so adding articles or
moving the address block in Excel does not break the build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

HEADER_CELL = "Artikelnummer"
DISTRIBUTOR_MARKER = "In Verkehrbringer:"


class WorkbookError(Exception):
    """The spreadsheet does not have the structure the build expects."""


@dataclass(frozen=True)
class Declaration:
    """The declaration in one language. Cells are text; blanks are ``""``."""

    title: str
    distributor_label: str
    distributor_lines: tuple[str, ...]
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def find_workbook(data_dir: Path) -> Path:
    """Return the single spreadsheet in ``data_dir``.

    Excel lock files (``~$name.xlsx``) are ignored. More than one real
    spreadsheet is an error rather than a guess about which one is current.
    """
    candidates = sorted(
        path for path in data_dir.glob("*.xlsx") if not path.name.startswith("~$")
    )
    if not candidates:
        raise WorkbookError(f"no .xlsx file found in {data_dir}")
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise WorkbookError(
            f"expected exactly one .xlsx in {data_dir}, found {len(candidates)}: {names}"
        )
    return candidates[0]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_declaration(path: Path) -> Declaration:
    """Parse the first worksheet of ``path`` into a :class:`Declaration`."""
    book = openpyxl.load_workbook(path, data_only=True)
    grid = [[_text(value) for value in row] for row in book.worksheets[0].iter_rows(values_only=True)]

    header_index = next(
        (index for index, row in enumerate(grid) if row and row[0] == HEADER_CELL),
        None,
    )
    if header_index is None:
        raise WorkbookError(
            f"{path.name}: no header row - expected a cell {HEADER_CELL!r} in column A"
        )

    columns: list[str] = []
    for cell in grid[header_index]:
        if not cell:
            break
        columns.append(cell)

    rows: list[tuple[str, ...]] = []
    for row in grid[header_index + 1:]:
        if not row or not row[0]:
            break
        rows.append(tuple(row[i] if i < len(row) else "" for i in range(len(columns))))

    return Declaration(
        title=grid[0][0] if grid and grid[0] else "",
        distributor_label=_distributor_label(grid, header_index),
        distributor_lines=_distributor_lines(grid, header_index),
        columns=tuple(columns),
        rows=tuple(rows),
    )


def _distributor_index(grid: list[list[str]], header_index: int) -> int | None:
    return next(
        (
            index
            for index, row in enumerate(grid[:header_index])
            if row and row[0] == DISTRIBUTOR_MARKER
        ),
        None,
    )


def _distributor_label(grid: list[list[str]], header_index: int) -> str:
    index = _distributor_index(grid, header_index)
    return DISTRIBUTOR_MARKER if index is not None else ""


def _distributor_lines(grid: list[list[str]], header_index: int) -> tuple[str, ...]:
    index = _distributor_index(grid, header_index)
    if index is None:
        return ()
    lines: list[str] = []
    for row in grid[index + 1: header_index]:
        if not row or not row[0]:
            break
        lines.append(row[0])
    return tuple(lines)
