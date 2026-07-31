"""Render declarations into the static site."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .workbook import Declaration

SITE_URL = "https://ppwr.jt-lizenzen.de/"
COMPANY_URL = "https://www.jt-lizenzen.de/"
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
            company_url=COMPANY_URL,
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
