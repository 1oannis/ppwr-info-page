# PPWR Packaging Conformity Page — Design

**Date:** 2026-07-31
**Status:** Approved

## Purpose

Publish the packaging conformity information for JT-Lizenzen packaging at
`https://ppwr.jt-lizenzen.de/`, in German and English, so that anyone receiving
one of our packages anywhere in the EU can scan a QR code on the box and read
the declaration for our packaging range.

The single source of truth is the spreadsheet `data/*.xlsx`. Dropping in a new
version of that file and pushing must be the entire process for publishing new
or changed packaging data.

## Success criteria

1. `ppwr.jt-lizenzen.de` serves the packaging table in German and English.
2. Replacing the xlsx and pushing to `main` republishes the site with no other
   manual step.
3. A new spreadsheet containing vocabulary the site cannot translate fails the
   build rather than publishing partially German English pages.
4. The page is readable on a phone held next to a package.
5. A printable QR sticker links to the page.

## Non-goals

- Per-article QR codes. One universal sticker goes on every package, including
  packages not yet listed. Keeping 19+ sticker designs matched to the right
  boxes is an operational risk with no benefit here.
- A search or filter box. At 19 rows scrolling is fine. Revisit if the table
  grows past a few dozen articles.
- Publishing the source xlsx for download.
- Any server-side component, database, or CMS.

## Architecture

Build-time static generation. A GitHub Actions workflow runs a Python script on
every push that touches the data or the site source. The script reads the
spreadsheet and the translation glossary, renders complete HTML for both
languages, and the workflow deploys the result to GitHub Pages.

The published site is inert HTML and CSS. It carries no data-processing logic:
no spreadsheet parsing, no translation, no rendering in the browser. The only
JavaScript is a language redirect on the entry page, and the site degrades to
working links without it.

### Alternatives considered

**Client-side xlsx parsing.** Ship the spreadsheet and parse it in the browser
with SheetJS. No build step at all — commit a file and it is live. Rejected
because it puts ~400 KB of JavaScript in front of someone scanning a box in a
warehouse, moves translation into the browser where a missing glossary term
silently renders German, and gives nothing the chance to validate the file
before it is public.

**Committed JSON intermediate.** The workflow converts xlsx to `data.json`,
commits it, and the page fetches it at runtime. Its real advantage is a
reviewable git diff of every data change. Rejected because it puts bot commits
on `main` and makes the page's content dependent on JavaScript. The diff
benefit is recovered for free by having the build print a row-level change
summary to the Actions log.

This decision is recorded as `docs/adr/0001-build-time-static-generation.md`.

## Repository layout

```
data/
  PPWR JT Lizenzen.xlsx       source of truth; found by glob, name irrelevant
  glossary.json               DE→EN vocabulary, hand-maintained
site/
  build.py                    xlsx + glossary → dist/
  templates/page.html.j2
  templates/ui-strings.json   page chrome (headings, toggle, footer) DE/EN
  static/style.css
  static/CNAME                ppwr.jt-lizenzen.de
tests/
  test_parse.py
  test_translate.py
.github/workflows/deploy.yml
docs/adr/0001-build-time-static-generation.md
```

Build output, not committed:

```
dist/
  index.html                  language redirect
  de/index.html
  en/index.html
  qr.svg
  labels.html                 A4 sheet of identical stickers
  style.css
  CNAME
```

## Components

### Spreadsheet reader

Locates the header row by searching for the cell `Artikelnummer` rather than
assuming a row number, takes the column names from that row, and reads data
rows until the first blank article number. The "In Verkehrbringer" block is
read from column A above the header row: the marker line, then the contiguous
non-empty lines below it. The document title is cell A1.

Consequence: inserting rows, adding articles, or moving the address block in
Excel does not break the build. Renaming a column does — deliberately, because
a renamed column has no translation.

Output: a plain data structure of `{title, distributor_lines, columns[], rows[]}`.
It knows nothing about translation or HTML.

### Translator

Input: the parsed structure plus `glossary.json`. Output: the same structure
rendered in one target language, or a list of translation failures.

Per cell, in order:

1. Columns listed in `passthrough_columns` emit verbatim — article numbers,
   dimensions, `Sorte` grade codes, FEFCO references. These are international
   notation and must not be altered.
2. Full-cell regex patterns with named groups.
3. Otherwise split the cell on commas and resolve each segment: segment-level
   patterns first, then exact term lookup.

Whitespace is normalised and trailing commas are stripped before lookup, then
re-appended, so the spreadsheet's punctuation artefacts (e.g.
`"Wellkiste (FEFCO 0201),"`) do not require their own glossary entries.

German output is the spreadsheet's own text, unmodified.

### Glossary

```json
{
  "columns": {
    "Artikelnummer": "Article number",
    "Recyclinganteil": "Recycled content"
  },
  "passthrough_columns": ["Artikelnummer", "Innenmaß", "Außenmaß", "Sorte"],
  "patterns": [
    {
      "de": "^Der Recyclinganteil an dieser Verpackung beträgt ca\\. (?P<n>[\\d.,]+)%$",
      "en": "The recycled content of this packaging is approx. {n}%"
    },
    {
      "de": "^Der Recyclinganteil an dieser Verpackung beträgt (?P<n>[\\d.,]+)%$",
      "en": "The recycled content of this packaging is {n}%"
    },
    {
      "de": "^(?P<g>[\\d.,]+) g (?P<mat>.+)$",
      "en": "{g} g {mat|term}"
    }
  ],
  "terms": {
    "Wellenstoff": "fluting",
    "geleimt": "glued"
  }
}
```

`{name|term}` in a replacement means the captured group is itself resolved
through `terms`. Optional wording such as "ca." is handled by ordered
alternative patterns rather than optional capture groups, so that no German
fragment can survive into an English sentence.

The glossary ships seeded with the full vocabulary of the current 19 rows, so
the first build passes.

### Number localisation

The spreadsheet uses German numeric notation: `1.714 g` means one thousand
seven hundred fourteen grams, and `1.190 x 430 x 270 mm` is a dimension over a
metre. Rendered unchanged on an English page, both read as values roughly a
thousand times too small. This is a correctness problem in a conformity
declaration, so number formatting is handled as its own step, independent of
word translation, and applies to passthrough columns too.

For the English rendering only:

- `\d{1,3}(\.\d{3})+` — German grouped thousands — becomes `,`-grouped.
- `\d+,\d+` — German decimal comma — becomes a decimal point.

The patterns are deliberately strict so that technical notation is untouched:
`VDW 1.40` has two digits after the separator and does not match the thousands
pattern, and `FEFCO 0201` and `C 1-4003 b/b` contain no separators at all. The
`Sorte` column is additionally exempted from number localisation, as it is pure
grade notation in which no value is a quantity.

### Renderer

A single Jinja2 template rendered once per language. Page chrome comes from
`ui-strings.json`; the article data comes from the translator.

### QR generator

`segno` (pure Python, no dependencies) emits `qr.svg` encoding
`https://ppwr.jt-lizenzen.de/`. Vector output scales to any sticker size
without pixelation. `labels.html` is a print-styled A4 sheet of identical
stickers, each carrying the QR, the wording "PPWR Konformitätserklärung /
Declaration of conformity", and the URL as text.

## The page

Content, in order: document title, the short PPWR introduction, the "In
Verkehrbringer" block, the article table, and the last-updated date.

The introduction is one or two sentences stating that the page carries
packaging conformity information under Regulation (EU) 2025/40, so that a
scanner who is not a compliance specialist understands what they are looking
at. Drafted during implementation and reviewed before merge.

The last-updated date comes from the committer date of the most recent commit
touching the xlsx, rendered per locale (`Stand: 31.07.2026` / `As of 31 July
2026`).

On desktop the articles are one table, one column per attribute. Below roughly
900 px each article collapses into a card headed by its article number with
labelled fields. Nine columns cannot be read on a phone, and a phone is the
device this will be scanned with.

A `DE | EN` toggle sits at the top right of each page and links to the same
content at the other language's URL.

### URLs and language selection

`/de/` and `/en/` are the stable canonical URLs. `/` is a minimal document that
calls `location.replace()` to `/de/` for German-language browsers and `/en/`
for everything else. `replace()` leaves no history entry, so the back button
cannot loop. Without JavaScript the page shows two plain links.

The QR encodes `/`, so the sticker artwork never has to change and the language
follows the scanner's own device.

## Failure behaviour

The build exits non-zero, printing file, row, column and offending text, on:

- no `data/*.xlsx`, or more than one
- no header row containing `Artikelnummer`
- a column header absent from `glossary.columns`
- any segment that resolves to neither a pattern nor a term

Example:

```
ERROR row 24, Fertigung: no translation for "heißsiegelbeschichtet"
      add it to data/glossary.json
```

A failed build does not deploy. The previously published, correct site stays
live while the glossary is corrected. This is the property that makes
"drop in a new xlsx and push" safe as an operating procedure.

## Testing

- Parser: header discovery at an arbitrary row position, distributor block
  extraction, stopping at the first blank article number, and the error raised
  when no header row exists.
- Translator: passthrough columns keep their wording, full-cell and segment
  patterns resolve, `{group|term}` nesting resolves, unknown segments are
  reported with row and column rather than silently passed through.
- Number localisation: `1.714` becomes `1,714` and `1.190 x 430 x 270` becomes
  `1,190 x 430 x 270` on the English page, while `VDW 1.40`, `FEFCO 0201` and
  `C 1-4003 b/b` are returned unchanged. German pages are byte-identical to the
  spreadsheet's own text.
- Build smoke test: building the committed spreadsheet produces both language
  pages containing all 19 article numbers, and the English page contains none
  of a set of German marker words.

## Deployment

`.github/workflows/deploy.yml` triggers on push to `main` under `data/**`,
`site/**`, and the workflow file itself, plus `workflow_dispatch`. It runs the
tests, runs the build, uploads `dist/` and deploys with `actions/deploy-pages`.
Pages source is already set to GitHub Actions.

### Manual setup outside the repository

1. Repo → Settings → Pages → Custom domain: `ppwr.jt-lizenzen.de`. Currently
   unset. Domain verification on the user profile is a separate thing and does
   not assign the domain to this repository.
2. The repository is private. Pages from a private repository requires GitHub
   Pro or higher. Making it public is the simpler option, since the content is
   intended to be publicly readable.

DNS already resolves `ppwr.jt-lizenzen.de` to `1oannis.github.io`, and HTTPS
enforcement is already enabled.
