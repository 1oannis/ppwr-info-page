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
