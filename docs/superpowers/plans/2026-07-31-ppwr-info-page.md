# PPWR Conformity Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the packaging conformity declaration at `https://ppwr.jt-lizenzen.de/` in German and English, regenerated automatically whenever the spreadsheet in `data/` changes.

**Architecture:** A Python package reads `data/*.xlsx`, translates it to English through a hand-maintained glossary, and renders complete static HTML into `dist/`. GitHub Actions runs the build on push and deploys `dist/` to GitHub Pages. The published site contains no data-processing logic — the only JavaScript is a language redirect on the entry page. Anything the glossary cannot translate fails the build, so a partially German English page can never be published.

**Tech Stack:** Python 3.13, openpyxl (spreadsheet), Jinja2 (templating), segno (QR), pytest. No frontend framework, no build tooling beyond pip.

**Spec:** `docs/superpowers/specs/2026-07-31-ppwr-info-page-design.md`

## Global Constraints

- Python 3.13. Dependencies: `openpyxl>=3.1.5`, `Jinja2>=3.1.4`, `segno>=1.6.1`, `pytest>=8.3` (dev only).
- The site URL is exactly `https://ppwr.jt-lizenzen.de/` (trailing slash). It appears in the QR payload, canonical links and hreflang alternates. Define it once as `SITE_URL` in `ppwr/render.py`; never hardcode it elsewhere.
- The custom domain is `ppwr.jt-lizenzen.de`, written to `site/static/CNAME` with no scheme, no trailing slash, and a trailing newline.
- German output must be byte-identical to the spreadsheet's own text. Only English output is transformed.
- Addresses (the "In Verkehrbringer" lines) are never translated and never number-localised.
- Jinja2 environments use `autoescape=True` and `undefined=StrictUndefined`. Spreadsheet content is rendered as text, never as markup.
- Article data lives only in `data/`. Never commit anything under `dist/` — it is gitignored.
- Every task ends with tests passing and a commit.

---

## File Structure

```text
pyproject.toml                     package metadata, dependencies, pytest config
ppwr/
  __init__.py
  workbook.py    reads data/*.xlsx  → Declaration; knows nothing of language or HTML
  numbers.py     German ⇄ English numeric notation; pure string function
  glossary.py    loads and validates data/glossary.json → Glossary
  translate.py   Declaration + Glossary → English Declaration, or TranslationError
  render.py      Declarations + templates → dist/ HTML and static assets
  qr.py          QR artwork and the printable sticker sheet
  build.py       CLI entry point; wires the above together
data/
  PPWR JT Lizenzen.xlsx            already committed
  glossary.json                    DE→EN vocabulary
site/
  templates/page.html.j2           the article page, rendered once per language
  templates/index.html.j2          language redirect at /
  templates/labels.html.j2         printable A4 sticker sheet
  templates/ui-strings.json        page chrome per language
  static/style.css
  static/CNAME
tests/
  test_workbook.py
  test_numbers.py
  test_translate.py
  test_build.py                    end-to-end against the committed spreadsheet
.github/workflows/deploy.yml
docs/adr/0001-build-time-static-generation.md
```

Each module has one responsibility and one direction of dependency: `build` → `render`/`qr` → `translate` → `glossary`/`numbers`/`workbook`. Nothing depends on `build`.

This differs from the spec, which sketched a single `site/build.py`. Splitting it into a `ppwr/` package keeps each file small enough to hold in context and lets the reader, the translator and the renderer be tested in isolation — `site/` is left holding only templates and static assets. The behaviour is identical.

---

### Task 1: Project scaffolding and spreadsheet reader

**Files:**
- Create: `pyproject.toml`
- Create: `ppwr/__init__.py`
- Create: `ppwr/workbook.py`
- Test: `tests/test_workbook.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Declaration` (frozen dataclass with fields `title: str`, `distributor_label: str`, `distributor_lines: tuple[str, ...]`, `columns: tuple[str, ...]`, `rows: tuple[tuple[str, ...], ...]`), `WorkbookError(Exception)`, `find_workbook(data_dir: Path) -> Path`, `read_declaration(path: Path) -> Declaration`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "ppwr"
version = "1.0.0"
description = "Static site generator for the JT-Lizenzen PPWR conformity declaration"
requires-python = ">=3.13"
dependencies = [
    "openpyxl>=3.1.5",
    "Jinja2>=3.1.4",
    "segno>=1.6.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.3"]

[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["ppwr"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create the empty package marker**

Create `ppwr/__init__.py` containing exactly:

```python
"""Static site generator for the JT-Lizenzen PPWR conformity declaration."""
```

- [ ] **Step 3: Install the project in editable mode**

Run: `python3 -m pip install -e ".[dev]"`
Expected: installs openpyxl, Jinja2, segno, pytest and the `ppwr` package.

- [ ] **Step 4: Write the failing tests**

Create `tests/test_workbook.py`:

```python
import openpyxl
import pytest

from ppwr.workbook import WorkbookError, find_workbook, read_declaration


def _workbook(tmp_path, rows, name="sheet.xlsx"):
    """Build a real .xlsx on disk from a list of row lists."""
    book = openpyxl.Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    path = tmp_path / name
    book.save(path)
    return path


def test_finds_header_regardless_of_its_row_position(tmp_path):
    path = _workbook(tmp_path, [
        ["Verpackungen nach PPWR"],
        [None],
        [None],
        ["Artikelnummer", "Fertigung"],
        ["00412488-01", "geleimt"],
    ])

    declaration = read_declaration(path)

    assert declaration.columns == ("Artikelnummer", "Fertigung")
    assert declaration.rows == (("00412488-01", "geleimt"),)


def test_reads_title_and_distributor_block(tmp_path):
    path = _workbook(tmp_path, [
        ["Verpackungen nach PPWR - Konformitaetserklaerungen"],
        [None],
        ["In Verkehrbringer:"],
        ["JT-Lizenzen - 1 A Fulfillment"],
        ["Wilhelmstr. 162"],
        [None],
        ["Artikelnummer"],
        ["00412488-01"],
    ])

    declaration = read_declaration(path)

    assert declaration.title == "Verpackungen nach PPWR - Konformitaetserklaerungen"
    assert declaration.distributor_label == "In Verkehrbringer:"
    assert declaration.distributor_lines == (
        "JT-Lizenzen - 1 A Fulfillment",
        "Wilhelmstr. 162",
    )


def test_stops_at_the_first_blank_article_number(tmp_path):
    path = _workbook(tmp_path, [
        ["Artikelnummer"],
        ["00412488-01"],
        ["00412490-01"],
        [None],
        ["00999999-01"],
    ])

    assert read_declaration(path).rows == (("00412488-01",), ("00412490-01",))


def test_blank_cells_become_empty_strings(tmp_path):
    path = _workbook(tmp_path, [
        ["Artikelnummer", "Aussenmass"],
        ["00412488-01", None],
    ])

    assert read_declaration(path).rows == (("00412488-01", ""),)


def test_missing_header_row_is_an_error(tmp_path):
    path = _workbook(tmp_path, [["Verpackungen"], ["no header anywhere"]])

    with pytest.raises(WorkbookError, match="no header row"):
        read_declaration(path)


def test_find_workbook_returns_the_single_spreadsheet(tmp_path):
    (tmp_path / "PPWR JT Lizenzen.xlsx").touch()

    assert find_workbook(tmp_path).name == "PPWR JT Lizenzen.xlsx"


def test_find_workbook_ignores_excel_lock_files(tmp_path):
    (tmp_path / "PPWR JT Lizenzen.xlsx").touch()
    (tmp_path / "~$PPWR JT Lizenzen.xlsx").touch()

    assert find_workbook(tmp_path).name == "PPWR JT Lizenzen.xlsx"


def test_find_workbook_rejects_an_empty_directory(tmp_path):
    with pytest.raises(WorkbookError, match="no .xlsx file"):
        find_workbook(tmp_path)


def test_find_workbook_rejects_more_than_one_spreadsheet(tmp_path):
    (tmp_path / "old.xlsx").touch()
    (tmp_path / "new.xlsx").touch()

    with pytest.raises(WorkbookError, match="expected exactly one"):
        find_workbook(tmp_path)
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_workbook.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ppwr.workbook'`

- [ ] **Step 6: Implement `ppwr/workbook.py`**

```python
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
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_workbook.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 8: Verify against the real spreadsheet**

Run:

```bash
python3 -c "
from pathlib import Path
from ppwr.workbook import find_workbook, read_declaration
d = read_declaration(find_workbook(Path('data')))
print(d.title)
print(d.distributor_label, d.distributor_lines)
print(len(d.columns), 'columns,', len(d.rows), 'rows')
"
```

Expected: the PPWR title, `In Verkehrbringer:` with 4 address lines, and `9 columns, 19 rows`.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml ppwr/__init__.py ppwr/workbook.py tests/test_workbook.py
git commit -m "feat: read the declaration spreadsheet into a Declaration"
```

---

### Task 2: German to English number notation

**Files:**
- Create: `ppwr/numbers.py`
- Test: `tests/test_numbers.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `localise(text: str) -> str`.

**Why this exists:** the spreadsheet writes `1.714 g` for one thousand seven hundred fourteen grams and `1.190 x 430 x 270 mm` for a box over a metre long. Left alone on an English page both read as values a thousand times too small. Board grades like `VDW 1.40` and `C 1-4003` must survive untouched, which is why the patterns are narrow rather than a blanket separator swap.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_numbers.py`:

```python
import pytest

from ppwr.numbers import localise


@pytest.mark.parametrize(
    ("german", "english"),
    [
        ("1.714", "1,714"),
        ("ca. 1.714 g pro Verpackung", "ca. 1,714 g pro Verpackung"),
        ("1.190 x 430 x 270 mm", "1,190 x 430 x 270 mm"),
        ("1.022 x 592 x 140 mm", "1,022 x 592 x 140 mm"),
        ("2,5", "2.5"),
        ("1.714,5", "1,714.5"),
    ],
)
def test_converts_german_numeric_notation(german, english):
    assert localise(german) == english


@pytest.mark.parametrize(
    "unchanged",
    [
        "C 1-4003 b/b / VDW 1.40 C",
        "BC 2-2005 b/b / VDW 2.20 BC",
        "Wellkiste (FEFCO 0201)",
        "72805 Lichtenstein",
        "Wilhelmstr. 162",
        "170 g Kraftliner braun",
        "592 x 462 x 384 mm",
        "600x400x200",
    ],
)
def test_leaves_technical_notation_alone(unchanged):
    assert localise(unchanged) == unchanged


def test_is_idempotent_on_already_english_notation():
    assert localise("1,714") == "1,714"
```

Note the last case: `1,714` looks like a German decimal comma, so a naive implementation flips it back to `1.714`. Guarding against a double pass is the point of the test — see the implementation note below.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_numbers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ppwr.numbers'`

- [ ] **Step 3: Implement `ppwr/numbers.py`**

```python
"""Convert German numeric notation into English convention.

Applied only when rendering English. German pages keep the spreadsheet's own
notation.
"""

from __future__ import annotations

import re

# A German number is either grouped thousands with an optional decimal comma
# (1.714, 1.714,5) or a bare decimal comma (2,5). Grouping requires exactly
# three digits after each separator, which keeps board grades such as
# "VDW 1.40" and article codes such as "C 1-4003" out of the match.
#
# The decimal branch allows at most two decimal places on purpose. Three would
# make "1,714" - already English grouping - look like a German decimal, so a
# second pass over converted text would flip it straight back.
_GERMAN_NUMBER = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?\b|\b\d+,\d{1,2}\b")

# str.translate swaps both separators in a single pass. Two chained str.replace
# calls would convert 1.714 to 1,714 and then straight back to 1.714.
_SWAP_SEPARATORS = str.maketrans({".": ",", ",": "."})


def localise(text: str) -> str:
    """Render any German-notation numbers in ``text`` in English convention."""
    return _GERMAN_NUMBER.sub(lambda match: match.group(0).translate(_SWAP_SEPARATORS), text)
```

This exact pattern was checked against all 15 test cases before the plan was written. Implement it as given rather than deriving your own — the two-decimal-place limit is what makes `test_is_idempotent_on_already_english_notation` pass, and a wider branch silently reverts `1,714` to `1.714`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_numbers.py -v`
Expected: PASS, 15 tests.

- [ ] **Step 5: Commit**

```bash
git add ppwr/numbers.py tests/test_numbers.py
git commit -m "feat: convert German numeric notation for English output"
```

---

### Task 3: Glossary and translator

**Files:**
- Create: `data/glossary.json`
- Create: `ppwr/glossary.py`
- Create: `ppwr/translate.py`
- Test: `tests/test_translate.py`

**Interfaces:**
- Consumes: `Declaration` from Task 1, `localise` from Task 2.
- Produces: `Glossary` (frozen dataclass), `GlossaryError(Exception)`, `load_glossary(path: Path) -> Glossary`, `translate(declaration: Declaration, glossary: Glossary) -> Declaration`, `TranslationError(Exception)` exposing `.failures: list[TranslationFailure]`.

- [ ] **Step 1: Create `data/glossary.json`**

This is the complete vocabulary of the 19 committed rows, so the first build passes. Regex patterns are tried before term lookup, first on the whole cell and then on each comma-separated segment.

```json
{
  "columns": {
    "Artikelnummer": "Article number",
    "Artikelbeschreibung": "Article description",
    "Fertigung": "Manufacture",
    "Innenmaß": "Internal dimensions",
    "Außenmaß": "External dimensions",
    "Sorte": "Board grade",
    "Recyclinganteil": "Recycled content",
    "Zusammensetzung": "Composition",
    "Gewicht (Toleranz: +/- 10%)": "Weight (tolerance: +/- 10%)"
  },
  "passthrough_columns": [
    "Artikelnummer",
    "Innenmaß",
    "Außenmaß",
    "Sorte"
  ],
  "no_number_localisation_columns": [
    "Sorte"
  ],
  "patterns": [
    {
      "de": "^Wellkiste \\(FEFCO (?P<code>\\d+)\\)$",
      "en": "Corrugated box (FEFCO {code})"
    },
    {
      "de": "^Stanzverpackung \\(FEFCO (?P<code>\\d+)\\)$",
      "en": "Die-cut packaging (FEFCO {code})"
    },
    {
      "de": "^Wellkiste mit (?P<size>[\\d.,]+) mm Zusatzriller vom Boden$",
      "en": "Corrugated box with {size} mm additional crease from the base"
    },
    {
      "de": "^Der Recyclinganteil an dieser Verpackung beträgt ca\\. (?P<share>[\\d.,]+)%$",
      "en": "The recycled content of this packaging is approx. {share}%"
    },
    {
      "de": "^Der Recyclinganteil an dieser Verpackung beträgt (?P<share>[\\d.,]+)%$",
      "en": "The recycled content of this packaging is {share}%"
    },
    {
      "de": "^ca\\. (?P<grams>[\\d.,]+) g pro Verpackung$",
      "en": "approx. {grams} g per packaging unit"
    },
    {
      "de": "^(?P<grams>[\\d.,]+) g (?P<material>.+)$",
      "en": "{grams} g {material|term}"
    }
  ],
  "terms": {
    "Verpackungen nach PPWR - Konformitätserklärungen": "Packaging under the PPWR — Declarations of conformity",
    "In Verkehrbringer:": "Placed on the market by:",
    "Wellkiste": "Corrugated box",
    "Stanzverpackung": "Die-cut packaging",
    "ohne Druck": "unprinted",
    "geleimt": "glued",
    "gebündelt": "bundled",
    "palettiert": "palletised",
    "unverschlossen": "unsealed",
    "Flexodruck 1-farbig": "flexo print, 1 colour",
    "Kraftliner braun": "brown kraftliner",
    "Testliner braun": "brown testliner",
    "Wellenstoff": "fluting"
  }
}
```

- [ ] **Step 2: Implement `ppwr/glossary.py`**

```python
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
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_translate.py`:

```python
import json

import pytest

from ppwr.glossary import load_glossary
from ppwr.translate import TranslationError, translate
from ppwr.workbook import Declaration


def make_glossary(tmp_path, **sections):
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps(sections, ensure_ascii=False), encoding="utf-8")
    return load_glossary(path)


def make_declaration(columns, rows, title="Titel", label="In Verkehrbringer:"):
    return Declaration(
        title=title,
        distributor_label=label,
        distributor_lines=("JT-Lizenzen", "Wilhelmstr. 162"),
        columns=columns,
        rows=rows,
    )


BASE_TERMS = {"Titel": "Title", "In Verkehrbringer:": "Placed on the market by:"}


def test_translates_column_headers(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Fertigung": "Manufacture"},
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Fertigung",), (("",),))

    assert translate(declaration, glossary).columns == ("Manufacture",)


def test_passthrough_columns_keep_their_text(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Sorte": "Board grade"},
        passthrough_columns=["Sorte"],
        no_number_localisation_columns=["Sorte"],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Sorte",), (("C 1-4003 b/b / VDW 1.40 C",),))

    assert translate(declaration, glossary).rows == (("C 1-4003 b/b / VDW 1.40 C",),)


def test_passthrough_columns_are_still_number_localised(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Innenmaß": "Internal dimensions"},
        passthrough_columns=["Innenmaß"],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Innenmaß",), (("1.190 x 430 x 270 mm",),))

    assert translate(declaration, glossary).rows == (("1,190 x 430 x 270 mm",),)


def test_matches_a_whole_cell_pattern(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Recyclinganteil": "Recycled content"},
        patterns=[{
            "de": r"^Der Recyclinganteil an dieser Verpackung beträgt ca\. (?P<share>[\d.,]+)%$",
            "en": "The recycled content of this packaging is approx. {share}%",
        }],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(
        ("Recyclinganteil",),
        (("Der Recyclinganteil an dieser Verpackung beträgt ca. 72%",),),
    )

    assert translate(declaration, glossary).rows == (
        ("The recycled content of this packaging is approx. 72%",),
    )


def test_splits_on_commas_and_looks_up_each_segment(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Fertigung": "Manufacture"},
        terms={**BASE_TERMS, "ohne Druck": "unprinted", "geleimt": "glued", "palettiert": "palletised"},
    )
    declaration = make_declaration(("Fertigung",), (("ohne Druck, geleimt, palettiert",),))

    assert translate(declaration, glossary).rows == (("unprinted, glued, palletised",),)


def test_resolves_a_captured_group_through_terms(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Zusammensetzung": "Composition"},
        patterns=[{"de": r"^(?P<grams>[\d.,]+) g (?P<material>.+)$", "en": "{grams} g {material|term}"}],
        terms={**BASE_TERMS, "Wellenstoff": "fluting", "Testliner braun": "brown testliner"},
    )
    declaration = make_declaration(
        ("Zusammensetzung",),
        (("100 g Wellenstoff, 120 g Testliner braun",),),
    )

    assert translate(declaration, glossary).rows == (
        ("100 g fluting, 120 g brown testliner",),
    )


def test_drops_a_trailing_comma_from_the_source(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Artikelbeschreibung": "Article description"},
        terms={**BASE_TERMS, "Stanzverpackung": "Die-cut packaging"},
    )
    declaration = make_declaration(("Artikelbeschreibung",), (("Stanzverpackung,",),))

    assert translate(declaration, glossary).rows == (("Die-cut packaging",),)


def test_addresses_are_never_translated(tmp_path):
    glossary = make_glossary(tmp_path, columns={"Artikelnummer": "Article number"}, terms=BASE_TERMS)
    declaration = make_declaration(("Artikelnummer",), (("00412488-01",),))

    assert translate(declaration, glossary).distributor_lines == ("JT-Lizenzen", "Wilhelmstr. 162")


def test_unknown_segment_reports_row_and_column(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Fertigung": "Manufacture"},
        terms={**BASE_TERMS, "geleimt": "glued"},
    )
    declaration = make_declaration(
        ("Fertigung",),
        (("geleimt",), ("geleimt, heißsiegelbeschichtet",)),
    )

    with pytest.raises(TranslationError) as caught:
        translate(declaration, glossary)

    failure = caught.value.failures[0]
    assert failure.row == 2
    assert failure.column == "Fertigung"
    assert failure.text == "heißsiegelbeschichtet"
    assert "heißsiegelbeschichtet" in str(caught.value)
    assert "glossary.json" in str(caught.value)


def test_unknown_column_header_is_reported(tmp_path):
    glossary = make_glossary(tmp_path, columns={}, terms=BASE_TERMS)
    declaration = make_declaration(("Kantenschutz",), (("",),))

    with pytest.raises(TranslationError, match="Kantenschutz"):
        translate(declaration, glossary)


def test_an_unresolvable_group_term_is_reported_not_silently_german(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Zusammensetzung": "Composition"},
        patterns=[{"de": r"^(?P<grams>[\d.,]+) g (?P<material>.+)$", "en": "{grams} g {material|term}"}],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Zusammensetzung",), (("100 g Schrenzpapier",),))

    with pytest.raises(TranslationError, match="Schrenzpapier"):
        translate(declaration, glossary)


def test_all_failures_are_collected_before_raising(tmp_path):
    glossary = make_glossary(tmp_path, columns={"Fertigung": "Manufacture"}, terms=BASE_TERMS)
    declaration = make_declaration(("Fertigung",), (("erstes",), ("zweites",)))

    with pytest.raises(TranslationError) as caught:
        translate(declaration, glossary)

    assert [failure.text for failure in caught.value.failures] == ["erstes", "zweites"]
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_translate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ppwr.translate'`

- [ ] **Step 5: Implement `ppwr/translate.py`**

```python
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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_translate.py -v`
Expected: PASS, 12 tests.

- [ ] **Step 7: Verify the real spreadsheet translates cleanly**

Run:

```bash
python3 -c "
from pathlib import Path
from ppwr.glossary import load_glossary
from ppwr.translate import translate
from ppwr.workbook import find_workbook, read_declaration
german = read_declaration(find_workbook(Path('data')))
english = translate(german, load_glossary(Path('data/glossary.json')))
print(english.title)
print(english.columns)
for row in english.rows[:3]:
    print(row)
"
```

Expected: no exception, English column headers, and rows reading e.g. `Corrugated box (FEFCO 0201)`, `unprinted, glued, bundled, palletised`, `approx. 917 g per packaging unit`. If a `TranslationError` appears, the glossary in Step 1 is incomplete — add the reported terms.

- [ ] **Step 8: Commit**

```bash
git add data/glossary.json ppwr/glossary.py ppwr/translate.py tests/test_translate.py
git commit -m "feat: translate the declaration to English via a glossary"
```

---

### Task 4: Templates, stylesheet and renderer

**Files:**
- Create: `site/templates/page.html.j2`
- Create: `site/templates/index.html.j2`
- Create: `site/templates/ui-strings.json`
- Create: `site/static/style.css`
- Create: `site/static/CNAME`
- Create: `ppwr/render.py`

**Interfaces:**
- Consumes: `Declaration` from Task 1.
- Produces: `SITE_URL: str`, `LANGUAGES: tuple[str, ...]`, `format_date(value: date, language: str) -> str`, `environment(templates_dir: Path) -> Environment` (Task 5 reuses it), `build_site(*, declarations: dict[str, Declaration], strings: dict, updated: date, templates_dir: Path, static_dir: Path, out_dir: Path) -> None`.

- [ ] **Step 1: Create `site/templates/ui-strings.json`**

The `intro` text is the only prose on the page that is not from the spreadsheet. Flag it for the repository owner to review before merge.

```json
{
  "de": {
    "page_title": "PPWR Konformitätserklärungen – JT-Lizenzen",
    "meta_description": "Verpackungsbezogene Konformitätsinformationen nach Verordnung (EU) 2025/40 (PPWR) für die von JT-Lizenzen in Verkehr gebrachten Verpackungen.",
    "intro": "Diese Seite enthält die verpackungsbezogenen Konformitätsinformationen nach der EU-Verpackungsverordnung (EU) 2025/40 (PPWR) für die nachstehend aufgeführten Verpackungen. Angegeben sind Aufbau, Materialzusammensetzung, Recyclinganteil und Gewicht je Verpackung.",
    "table_caption": "Verpackungen und ihre Konformitätsangaben",
    "updated_label": "Stand",
    "switch_label": "English",
    "switch_title": "Show this page in English",
    "empty_cell": "–"
  },
  "en": {
    "page_title": "PPWR declarations of conformity – JT-Lizenzen",
    "meta_description": "Packaging conformity information under Regulation (EU) 2025/40 (PPWR) for packaging placed on the market by JT-Lizenzen.",
    "intro": "This page provides the packaging conformity information required by the EU Packaging and Packaging Waste Regulation (EU) 2025/40 (PPWR) for the packaging listed below. It states the construction, material composition, recycled content and weight of each packaging unit.",
    "table_caption": "Packaging and its conformity data",
    "updated_label": "As of",
    "switch_label": "Deutsch",
    "switch_title": "Diese Seite auf Deutsch anzeigen",
    "empty_cell": "–"
  }
}
```

- [ ] **Step 2: Create `site/templates/page.html.j2`**

```jinja
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ t.page_title }}</title>
<meta name="description" content="{{ t.meta_description }}">
<link rel="canonical" href="{{ site_url }}{{ lang }}/">
<link rel="alternate" hreflang="de" href="{{ site_url }}de/">
<link rel="alternate" hreflang="en" href="{{ site_url }}en/">
<link rel="alternate" hreflang="x-default" href="{{ site_url }}">
<link rel="stylesheet" href="../style.css">
</head>
<body>
<header class="masthead">
  <a class="switch" href="../{{ other }}/" hreflang="{{ other }}" title="{{ t.switch_title }}">{{ t.switch_label }}</a>
  <h1>{{ declaration.title }}</h1>
  <p class="intro">{{ t.intro }}</p>
  {% if declaration.distributor_lines %}
  <section class="distributor">
    <h2>{{ declaration.distributor_label }}</h2>
    {% for line in declaration.distributor_lines %}
    <p>{{ line }}</p>
    {% endfor %}
  </section>
  {% endif %}
</header>
<main>
  <table>
    <caption>{{ t.table_caption }}</caption>
    <thead>
      <tr>
        {% for column in declaration.columns %}
        <th scope="col">{{ column }}</th>
        {% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in declaration.rows %}
      <tr>
        {% for cell in row %}
        <td data-label="{{ declaration.columns[loop.index0] }}">{{ cell if cell else t.empty_cell }}</td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</main>
<footer>
  <p>{{ t.updated_label }}: {{ updated }}</p>
</footer>
</body>
</html>
```

- [ ] **Step 3: Create `site/templates/index.html.j2`**

`location.replace` leaves no history entry, so the back button cannot bounce the visitor between `/` and the language page.

```jinja
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPWR – JT-Lizenzen</title>
<link rel="alternate" hreflang="de" href="{{ site_url }}de/">
<link rel="alternate" hreflang="en" href="{{ site_url }}en/">
<link rel="alternate" hreflang="x-default" href="{{ site_url }}">
<link rel="stylesheet" href="style.css">
<script>
  (function () {
    var tags = navigator.languages || [navigator.language || "en"];
    var german = String(tags[0] || "en").toLowerCase().indexOf("de") === 0;
    location.replace(german ? "de/" : "en/");
  })();
</script>
</head>
<body>
<main class="chooser">
  <h1>PPWR</h1>
  <p><a href="de/">Deutsch</a> · <a href="en/">English</a></p>
</main>
</body>
</html>
```

- [ ] **Step 4: Create `site/static/CNAME`**

A single line, no scheme, with a trailing newline:

```text
ppwr.jt-lizenzen.de
```

- [ ] **Step 5: Create `site/static/style.css`**

Nine columns cannot be read on a phone, and a phone is the device this gets scanned with. Below 900px each row becomes a card headed by its article number, using the `data-label` attribute the template emits.

```css
:root {
  --ink: #16191d;
  --muted: #5b6470;
  --rule: #d7dce3;
  --surface: #ffffff;
  --accent: #0b5c3f;
  --page: #f6f7f9;
}

* { box-sizing: border-box; }

html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  padding: 2rem 1.25rem 4rem;
  background: var(--page);
  color: var(--ink);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

.masthead, main, footer { max-width: 78rem; margin-inline: auto; }

h1 {
  margin: 0 0 0.75rem;
  font-size: clamp(1.5rem, 1.1rem + 1.6vw, 2.25rem);
  line-height: 1.2;
}

.intro { max-width: 46rem; color: var(--muted); }

.switch {
  float: right;
  padding: 0.4rem 0.85rem;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: var(--surface);
  color: var(--accent);
  font-weight: 600;
  text-decoration: none;
}

.switch:hover, .switch:focus { border-color: var(--accent); }

.distributor {
  margin: 1.5rem 0 2rem;
  padding: 1rem 1.25rem;
  border-left: 3px solid var(--accent);
  background: var(--surface);
}

.distributor h2 { margin: 0 0 0.5rem; font-size: 0.95rem; color: var(--muted); }
.distributor p { margin: 0; }

table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  font-size: 0.9rem;
}

caption {
  caption-side: top;
  padding-bottom: 0.75rem;
  text-align: left;
  font-weight: 600;
}

th, td {
  padding: 0.6rem 0.7rem;
  border: 1px solid var(--rule);
  text-align: left;
  vertical-align: top;
}

thead th {
  position: sticky;
  top: 0;
  background: var(--accent);
  color: #fff;
  font-size: 0.8rem;
  letter-spacing: 0.01em;
}

tbody tr:nth-child(even) { background: #fbfcfd; }

td:first-child { font-variant-numeric: tabular-nums; white-space: nowrap; font-weight: 600; }

footer { margin-top: 2rem; color: var(--muted); font-size: 0.875rem; }

.chooser { padding-top: 4rem; text-align: center; }

@media (max-width: 900px) {
  table, caption, thead, tbody, tr, td { display: block; width: 100%; }

  thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }

  tr {
    margin-bottom: 1rem;
    border: 1px solid var(--rule);
    background: var(--surface);
  }

  tbody tr:nth-child(even) { background: var(--surface); }

  td { border: 0; border-top: 1px solid var(--rule); padding: 0.6rem 0.9rem; }

  td::before {
    display: block;
    color: var(--muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    content: attr(data-label);
  }

  td:first-child {
    border-top: 0;
    background: var(--accent);
    color: #fff;
    font-size: 1rem;
  }

  td:first-child::before { display: none; }
}

@media print {
  body { padding: 0; background: #fff; font-size: 10pt; }
  .switch { display: none; }
  thead th { position: static; background: #eee; color: #000; }
  tr { break-inside: avoid; }
}
```

- [ ] **Step 6: Implement `ppwr/render.py`**

`locale`-based month names are unreliable in CI containers, so English month names are a literal tuple and German uses numeric format.

```python
"""Render declarations into the static site."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .workbook import Declaration

SITE_URL = "https://ppwr.jt-lizenzen.de/"
LANGUAGES = ("de", "en")

_ENGLISH_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def format_date(value: date, language: str) -> str:
    """Format ``value`` the way a reader of ``language`` expects it."""
    if language == "de":
        return value.strftime("%d.%m.%Y")
    return f"{value.day} {_ENGLISH_MONTHS[value.month - 1]} {value.year}"


def environment(templates_dir: Path) -> Environment:
    """A Jinja environment that escapes spreadsheet content and rejects typos."""
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_site(
    *,
    declarations: dict[str, Declaration],
    strings: dict[str, dict[str, str]],
    updated: date,
    templates_dir: Path,
    static_dir: Path,
    out_dir: Path,
) -> None:
    """Write the complete site into ``out_dir``, replacing anything already there."""
    env = environment(templates_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    page = env.get_template("page.html.j2")
    for language in LANGUAGES:
        other = "en" if language == "de" else "de"
        html = page.render(
            lang=language,
            other=other,
            declaration=declarations[language],
            t=strings[language],
            updated=format_date(updated, language),
            site_url=SITE_URL,
        )
        target = out_dir / language
        target.mkdir()
        (target / "index.html").write_text(html, encoding="utf-8")

    (out_dir / "index.html").write_text(
        env.get_template("index.html.j2").render(site_url=SITE_URL),
        encoding="utf-8",
    )

    for asset in sorted(static_dir.iterdir()):
        if asset.is_file():
            shutil.copy2(asset, out_dir / asset.name)
```

- [ ] **Step 7: Verify rendering by hand**

Run:

```bash
python3 -c "
import json
from datetime import date
from pathlib import Path
from ppwr.glossary import load_glossary
from ppwr.render import build_site
from ppwr.translate import translate
from ppwr.workbook import find_workbook, read_declaration
german = read_declaration(find_workbook(Path('data')))
english = translate(german, load_glossary(Path('data/glossary.json')))
build_site(
    declarations={'de': german, 'en': english},
    strings=json.loads(Path('site/templates/ui-strings.json').read_text(encoding='utf-8')),
    updated=date(2026, 7, 31),
    templates_dir=Path('site/templates'),
    static_dir=Path('site/static'),
    out_dir=Path('dist'),
)
print(sorted(p.relative_to('dist').as_posix() for p in Path('dist').rglob('*')))
"
python3 -m http.server 8000 --directory dist
```

Expected: the file list contains `CNAME`, `de/index.html`, `en/index.html`, `index.html`, `style.css`. Open `http://localhost:8000/`, confirm it redirects by browser language, that the `DE | EN` toggle moves between the two, and that narrowing the window below 900px turns the table into cards. Stop the server with Ctrl-C.

- [ ] **Step 8: Commit**

```bash
git add site/ ppwr/render.py
git commit -m "feat: render the bilingual conformity page"
```

---

### Task 5: QR code and printable sticker sheet

**Files:**
- Create: `ppwr/qr.py`
- Create: `site/templates/labels.html.j2`

**Interfaces:**
- Consumes: `environment` from Task 4.
- Produces: `write_qr(url: str, out_dir: Path) -> str` returning the SVG markup, and `write_labels(qr_svg: str, url: str, templates_dir: Path, out_dir: Path) -> None`.

Error correction level `h` (30% recoverable) is deliberate: these stickers get taped over, scuffed and rained on in transit.

- [ ] **Step 1: Create `site/templates/labels.html.j2`**

```jinja
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>PPWR QR-Etiketten / QR labels</title>
<style>
  @page { size: A4; margin: 10mm; }
  body { margin: 0; font: 9pt/1.3 system-ui, sans-serif; }
  .sheet { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; }
  .label {
    display: flex;
    gap: 3mm;
    align-items: center;
    padding: 3mm;
    border: 0.2mm dashed #999;
    break-inside: avoid;
  }
  .label svg { width: 22mm; height: 22mm; }
  .label p { margin: 0 0 0.5mm; }
  .label .title { font-weight: 700; }
  .label .url { font-size: 7.5pt; word-break: break-all; }
  @media print { .label { border-color: #ccc; } }
</style>
</head>
<body>
<div class="sheet">
  {% for _ in range(count) %}
  <div class="label">
    {{ qr_svg | safe }}
    <div>
      <p class="title">PPWR</p>
      <p>Konformitätserklärung</p>
      <p>Declaration of conformity</p>
      <p class="url">{{ url }}</p>
    </div>
  </div>
  {% endfor %}
</div>
</body>
</html>
```

- [ ] **Step 2: Implement `ppwr/qr.py`**

```python
"""QR artwork for the package sticker, and a printable sheet of stickers."""

from __future__ import annotations

import io
from pathlib import Path

import segno

from .render import environment

LABELS_PER_SHEET = 21

# Level "h" recovers 30% of a damaged symbol. These stickers travel on the
# outside of boxes, so the extra redundancy is worth the density.
_ERROR_CORRECTION = "h"


def _svg_markup(code: segno.QRCode) -> str:
    buffer = io.BytesIO()
    code.save(
        buffer,
        kind="svg",
        xmldecl=False,
        svgns=True,
        scale=8,
        border=2,
        dark="#000000",
        light=None,
    )
    return buffer.getvalue().decode("utf-8")


def write_qr(url: str, out_dir: Path) -> str:
    """Write ``qr.svg`` into ``out_dir`` and return its markup for inlining."""
    markup = _svg_markup(segno.make(url, error=_ERROR_CORRECTION))
    (out_dir / "qr.svg").write_text(markup, encoding="utf-8")
    return markup


def write_labels(qr_svg: str, url: str, templates_dir: Path, out_dir: Path) -> None:
    """Write a print-ready A4 sheet of identical stickers."""
    html = environment(templates_dir).get_template("labels.html.j2").render(
        qr_svg=qr_svg,
        url=url,
        count=LABELS_PER_SHEET,
    )
    (out_dir / "labels.html").write_text(html, encoding="utf-8")
```

- [ ] **Step 3: Verify the QR scans**

Run:

```bash
python3 -c "
from pathlib import Path
from ppwr.qr import write_labels, write_qr
from ppwr.render import SITE_URL
out = Path('dist'); out.mkdir(exist_ok=True)
svg = write_qr(SITE_URL, out)
write_labels(svg, SITE_URL, Path('site/templates'), out)
print('qr.svg', (out / 'qr.svg').stat().st_size, 'bytes')
print('labels.html', (out / 'labels.html').stat().st_size, 'bytes')
"
open dist/labels.html
```

Expected: both files written; `labels.html` opens showing a 3-column grid of 21 identical stickers. **Scan one with a phone** and confirm it opens `https://ppwr.jt-lizenzen.de/`. Also use the browser's print preview to confirm the stickers fit one A4 page without clipping.

- [ ] **Step 4: Commit**

```bash
git add ppwr/qr.py site/templates/labels.html.j2
git commit -m "feat: generate the QR sticker and printable label sheet"
```

---

### Task 6: Build entry point and end-to-end test

**Files:**
- Create: `ppwr/build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: `main(argv: list[str] | None = None) -> int`, `last_updated(path: Path) -> date`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_build.py`:

```python
from pathlib import Path

from ppwr import build

GERMAN_MARKERS = (
    "Wellkiste",
    "Stanzverpackung",
    "geleimt",
    "gebündelt",
    "palettiert",
    "beträgt",
    "Wellenstoff",
    "Testliner braun",
    "Kraftliner braun",
    "Recyclinganteil",
    "Artikelnummer",
    "Innenmaß",
)

ARTICLE_NUMBERS = (
    "00412488-01", "00412490-01", "00412491-01", "00412492-01", "00412493-01",
    "00440528-01", "00440533-01", "00448685-01", "00453666-01", "00453667-01",
    "00469859-01", "00469860-01", "00469861-01", "00473038-01", "00476810-01",
    "00476935-01", "00477037-01", "00483144-01", "00483153-01",
)


def build_into(tmp_path):
    out = tmp_path / "dist"
    assert build.main(["--out", str(out)]) == 0
    return out


def test_build_writes_every_expected_file(tmp_path):
    out = build_into(tmp_path)

    for name in ("index.html", "de/index.html", "en/index.html", "style.css", "CNAME", "qr.svg", "labels.html"):
        assert (out / name).is_file(), f"missing {name}"


def test_both_languages_list_every_article(tmp_path):
    out = build_into(tmp_path)

    for language in ("de", "en"):
        page = (out / language / "index.html").read_text(encoding="utf-8")
        for number in ARTICLE_NUMBERS:
            assert number in page, f"{number} missing from {language}"


def test_the_english_page_has_no_german_left(tmp_path):
    page = (build_into(tmp_path) / "en" / "index.html").read_text(encoding="utf-8")

    for marker in GERMAN_MARKERS:
        assert marker not in page, f"untranslated German on the English page: {marker}"


def test_the_english_page_uses_english_number_notation(tmp_path):
    page = (build_into(tmp_path) / "en" / "index.html").read_text(encoding="utf-8")

    assert "1,190 x 430 x 270 mm" in page
    assert "1.190 x 430 x 270 mm" not in page


def test_the_german_page_keeps_the_spreadsheets_own_notation(tmp_path):
    page = (build_into(tmp_path) / "de" / "index.html").read_text(encoding="utf-8")

    assert "1.190 x 430 x 270 mm" in page
    assert "Der Recyclinganteil an dieser Verpackung beträgt ca. 72%" in page


def test_the_address_is_not_translated(tmp_path):
    page = (build_into(tmp_path) / "en" / "index.html").read_text(encoding="utf-8")

    assert "Wilhelmstr. 162" in page
    assert "72805 Lichtenstein" in page


def test_the_cname_names_the_custom_domain(tmp_path):
    assert (build_into(tmp_path) / "CNAME").read_text(encoding="utf-8").strip() == "ppwr.jt-lizenzen.de"


def test_the_qr_encodes_the_site_url(tmp_path):
    labels = (build_into(tmp_path) / "labels.html").read_text(encoding="utf-8")

    assert "https://ppwr.jt-lizenzen.de/" in labels
    assert "<svg" in labels


def test_a_missing_spreadsheet_fails_the_build(tmp_path, capsys):
    empty = tmp_path / "data"
    empty.mkdir()

    assert build.main(["--data", str(empty), "--out", str(tmp_path / "dist")]) == 1
    assert "no .xlsx file" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ppwr.build'`

- [ ] **Step 3: Implement `ppwr/build.py`**

```python
"""Build the static site from the spreadsheet.

Run as ``python -m ppwr.build``. Exits non-zero with a diagnostic on stderr if
the spreadsheet or the glossary cannot produce a complete site, so a failing
build leaves the previously published site untouched.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .glossary import GlossaryError, load_glossary
from .qr import write_labels, write_qr
from .render import SITE_URL, build_site
from .translate import TranslationError, translate
from .workbook import WorkbookError, find_workbook, read_declaration

ROOT = Path(__file__).resolve().parent.parent


def last_updated(path: Path) -> date:
    """The committer date of the last commit touching ``path``.

    Falls back to the file's modification time when git history is unavailable,
    which happens in a shallow CI checkout or a plain unpacked copy. The
    workflow checks out full history so the committed date is used there.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stamp = result.stdout.strip()
        if stamp:
            return datetime.fromisoformat(stamp).date()
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PPWR conformity site.")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)

    try:
        source = find_workbook(args.data)
        german = read_declaration(source)
        glossary = load_glossary(args.data / "glossary.json")
        english = translate(german, glossary)
    except (WorkbookError, GlossaryError, TranslationError) as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1

    templates_dir = args.site / "templates"
    strings = json.loads((templates_dir / "ui-strings.json").read_text(encoding="utf-8"))

    build_site(
        declarations={"de": german, "en": english},
        strings=strings,
        updated=last_updated(source),
        templates_dir=templates_dir,
        static_dir=args.site / "static",
        out_dir=args.out,
    )
    write_labels(write_qr(SITE_URL, args.out), SITE_URL, templates_dir, args.out)

    print(f"built {len(german.rows)} articles from {source.name} into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: PASS, all tests across the four test files.

- [ ] **Step 5: Confirm the failure path reports usefully**

Temporarily remove a term to prove the build refuses to publish half-translated English:

```bash
python3 - <<'PY'
import json, pathlib
path = pathlib.Path("data/glossary.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["terms"].pop("geleimt")
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
python3 -m ppwr.build; echo "exit code: $?"
git checkout data/glossary.json
```

Expected: exit code 1 and a message naming `geleimt` with its row and column, followed by `add them to data/glossary.json`. Confirm `git checkout` restores the glossary and `python3 -m ppwr.build` then succeeds.

- [ ] **Step 6: Commit**

```bash
git add ppwr/build.py tests/test_build.py
git commit -m "feat: add the build entry point and end-to-end test"
```

---

### Task 7: Deployment workflow, ADR and README

**Files:**
- Create: `.github/workflows/deploy.yml`
- Create: `docs/adr/0001-build-time-static-generation.md`
- Create: `README.md`

**Interfaces:**
- Consumes: `python -m ppwr.build` from Task 6.
- Produces: a deployed site. Nothing in the repository depends on this task.

- [ ] **Step 1: Create `.github/workflows/deploy.yml`**

`fetch-depth: 0` is required — `last_updated` reads git history for the spreadsheet's commit date, and a shallow checkout silently falls back to the checkout's file mtime.

```yaml
name: Deploy

on:
  push:
    branches: [main]
    paths:
      - "data/**"
      - "ppwr/**"
      - "site/**"
      - "tests/**"
      - "pyproject.toml"
      - ".github/workflows/deploy.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip

      - name: Install
        run: python -m pip install -e ".[dev]"

      - name: Test
        run: python -m pytest -q

      - name: Build
        run: python -m ppwr.build --out dist

      - uses: actions/configure-pages@v5
        with:
          enablement: true

      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Create `docs/adr/0001-build-time-static-generation.md`**

```markdown
# ADR 0001: Generate the conformity page at build time

**Status:** Accepted
**Date:** 2026-07-31

## Context

The packaging conformity declaration lives in a spreadsheet that changes
whenever packaging is added or altered. It must be published publicly in German
and English, and read from a phone by anyone who scans a QR code on a package
anywhere in the EU. The German source text is free text with a small, highly
repetitive vocabulary.

## Decision

A build step converts the spreadsheet into complete static HTML for both
languages, run by GitHub Actions on every push and deployed to GitHub Pages.
Translation is driven by a glossary in the repository. Any term the glossary
cannot resolve fails the build.

## Consequences

The published page is inert HTML: it works with JavaScript disabled, prints
cleanly, and cannot render a half-translated table, because a build that cannot
translate everything never produces artefacts to deploy. The previously
published site stays live while the glossary is corrected.

The cost is a glossary that must be extended when genuinely new packaging
vocabulary appears. Given the vocabulary of the current range — 13 terms and 7
patterns cover all 19 articles — this is a small, and deliberately visible,
maintenance burden.

## Alternatives considered

**Parse the spreadsheet in the browser.** Ship the xlsx and read it with
SheetJS. Requires no build step at all. Rejected: it puts roughly 400 KB of
JavaScript in front of someone scanning a box, moves translation to the client
where an unknown term silently renders German, and nothing validates the file
before it is public.

**Commit a generated JSON file.** Convert the spreadsheet to JSON in CI, commit
it, and fetch it from the page. Gives a reviewable diff of every data change.
Rejected: it puts bot commits on `main` and makes page content depend on
JavaScript. The diff benefit is recovered by having the build log the article
count it produced.
```

- [ ] **Step 3: Create `README.md`**

````markdown
# PPWR conformity page

Publishes the JT-Lizenzen packaging conformity declaration at
<https://ppwr.jt-lizenzen.de/> in German and English.

## Publishing new packaging data

1. Replace the spreadsheet in `data/` (any `.xlsx` name; exactly one file).
2. Commit and push to `main`.

GitHub Actions rebuilds and deploys. If the spreadsheet contains vocabulary the
glossary does not know, the build fails with the offending row, column and text,
and the live site is left untouched until `data/glossary.json` is extended.

## Local build

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m ppwr.build
python3 -m http.server 8000 --directory dist
```

## QR stickers

`dist/labels.html` is a print-ready A4 sheet of identical stickers, and
`dist/qr.svg` is the artwork on its own. Every sticker points at the site root,
which redirects to German or English based on the scanner's device, so one
sticker design works on every package.

## Layout

| Path              | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| `data/`           | the spreadsheet and the DE→EN glossary           |
| `ppwr/`           | the build: read, translate, render, QR           |
| `site/`           | templates, stylesheet, `CNAME`                   |
| `docs/adr/`       | architecture decisions                           |

See `docs/adr/0001-build-time-static-generation.md` for why the site is
generated rather than assembled in the browser.
````

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/deploy.yml docs/adr/0001-build-time-static-generation.md README.md
git commit -m "ci: build and deploy the site to GitHub Pages"
git push -u origin main
```

- [ ] **Step 5: Verify the deployment**

Run: `gh run watch`
Expected: both jobs green.

Then confirm the live site:

```bash
gh api repos/1oannis/ppwr-info-page/pages --jq '{status, cname, https_enforced}'
curl -sI https://ppwr.jt-lizenzen.de/ | head -1
curl -s https://ppwr.jt-lizenzen.de/en/ | grep -c "00412488-01"
```

Expected: `status` is `built`, `cname` is `ppwr.jt-lizenzen.de`, the curl returns `200`, and the article number is found. If `https_enforced` is still `false`, tick **Enforce HTTPS** in Settings → Pages once the certificate has been issued.

- [ ] **Step 6: Scan the deployed QR**

Open `https://ppwr.jt-lizenzen.de/labels.html`, scan a sticker with a phone, and confirm it lands on the live page in the phone's language. This is the one check no test can make.

---

## Verification checklist

Run before considering the work done:

- [ ] `python3 -m pytest` — all tests pass
- [ ] `python3 -m ppwr.build` — exits 0, reports 19 articles
- [ ] Removing a glossary term makes the build exit 1 naming that term
- [ ] `https://ppwr.jt-lizenzen.de/` redirects to `/de/` or `/en/` by browser language
- [ ] Both language pages list all 19 article numbers
- [ ] The English page contains no German markers and shows `1,190 x 430 x 270 mm`
- [ ] The German page is unchanged from the spreadsheet text
- [ ] The table becomes cards below 900px on a real phone
- [ ] A printed sticker scans and opens the live site
- [ ] Enforce HTTPS is enabled in Settings → Pages

## Owner review items

Two pieces of prose are written by the implementer rather than taken from the
spreadsheet, and should be read by the repository owner before merge:

- `site/templates/ui-strings.json` → `intro`, both languages. States what the
  page is and cites Regulation (EU) 2025/40.
- The English column headers and terms in `data/glossary.json`, particularly
  `Sorte` → "Board grade" and `Fertigung` → "Manufacture", which are trade terms
  where a supplier may prefer different wording.
