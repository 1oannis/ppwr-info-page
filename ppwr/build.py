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

from .branding import BrandingError, write_favicons
from .glossary import GlossaryError, load_glossary
from .qr import write_qr
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
    static_dir = args.site / "static"
    strings = json.loads((templates_dir / "ui-strings.json").read_text(encoding="utf-8"))

    build_site(
        declarations={"de": german, "en": english},
        strings=strings,
        updated=last_updated(source),
        templates_dir=templates_dir,
        static_dir=static_dir,
        out_dir=args.out,
    )
    write_qr(SITE_URL, args.out)

    try:
        write_favicons(static_dir / "logo.png", args.out)
    except BrandingError as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1

    print(f"built {len(german.rows)} articles from {source.name} into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
