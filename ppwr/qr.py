"""QR artwork for the packaging label, in the formats a print shop accepts.

SVG is the master: vector, so it scales to any size without pixelation. PNG
and JPEG are rasterised from the same symbol for tools that will not take
vector input.
"""

from __future__ import annotations

import io
from pathlib import Path

import segno
from PIL import Image

# Level "h" recovers 30% of a damaged symbol. The code is printed on invoices
# and packaging that get folded, stamped and scuffed, so the redundancy is
# worth the extra density.
_ERROR_CORRECTION = "h"

# ISO/IEC 18004's recommended quiet zone. Scanners need the white margin.
_QUIET_ZONE = 4

# 20 px per module puts the raster files near 1000 px square, which prints
# cleanly at roughly 8 cm / 300 dpi - comfortably more than an invoice needs.
_RASTER_SCALE = 20

# JPEG is lossy and a QR code is exactly the high-contrast edge detail it
# handles worst. At this size and quality the artefacts stay far below a
# module, but prefer PNG or SVG wherever the tool accepts them.
_JPEG_QUALITY = 95


def _svg_markup(code: segno.QRCode) -> str:
    """SVG with a viewBox and no intrinsic size, so CSS can scale it freely.

    Without ``omitsize`` segno emits fixed width/height and no viewBox, and a
    browser then crops such an SVG instead of scaling it when CSS overrides
    its size.
    """
    buffer = io.BytesIO()
    code.save(
        buffer,
        kind="svg",
        xmldecl=False,
        svgns=True,
        scale=8,
        border=_QUIET_ZONE,
        dark="#000000",
        light=None,
        omitsize=True,
    )
    return buffer.getvalue().decode("utf-8")


def _png_bytes(code: segno.QRCode) -> bytes:
    buffer = io.BytesIO()
    code.save(
        buffer,
        kind="png",
        scale=_RASTER_SCALE,
        border=_QUIET_ZONE,
        dark="#000000",
        light="#ffffff",
    )
    return buffer.getvalue()


def write_qr(url: str, out_dir: Path) -> str:
    """Write ``qr.svg``, ``qr.png`` and ``qr.jpg`` into ``out_dir``.

    Returns the SVG markup so the page can inline it.
    """
    code = segno.make(url, error=_ERROR_CORRECTION)

    markup = _svg_markup(code)
    (out_dir / "qr.svg").write_text(markup, encoding="utf-8")

    png = _png_bytes(code)
    (out_dir / "qr.png").write_bytes(png)

    # JPEG has no alpha channel, so flatten onto white rather than letting
    # Pillow guess - a transparent quiet zone would come out black.
    raster = Image.open(io.BytesIO(png)).convert("RGB")
    raster.save(out_dir / "qr.jpg", format="JPEG", quality=_JPEG_QUALITY, subsampling=0)

    return markup
