"""Derive the favicon from the company logo.

The logo is the single source of truth: the favicon is the orange "JT-" ball
at its left edge, cropped at build time rather than maintained as a separate
image that could drift out of sync.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

# Bounding box of the orange ball in `site/static/logo.png` (480x213), chosen
# to centre the ball and keep the whole "JT-" legible. Pixel coordinates are
# unavoidable here; `_assert_is_the_ball` fails the build if a replacement
# logo moves the mark, rather than silently shipping a favicon of whitespace.
_BALL_BOX = (36, 45, 160, 169)

# Sizes browsers actually request: 16/32 for the tab, 180 for an iOS home
# screen bookmark.
_ICO_SIZES = ((16, 16), (32, 32), (48, 48))
_TOUCH_ICON_SIZE = 180


class BrandingError(Exception):
    """The logo is missing or does not look like the logo we expect."""


def _is_orange(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return alpha > 128 and red > 190 and 60 < green < 150 and blue < 80


def _assert_is_the_ball(crop: Image.Image, source: Path) -> None:
    """Fail loudly if the crop is not predominantly the orange mark."""
    pixels = crop.load()
    width, height = crop.size
    orange = sum(
        1
        for y in range(height)
        for x in range(width)
        if _is_orange(pixels[x, y])
    )
    share = orange / (width * height)
    if share < 0.25:
        raise BrandingError(
            f"{source.name}: only {share:.0%} of the favicon crop {_BALL_BOX} is "
            "orange, so the logo has probably changed - update _BALL_BOX in "
            "ppwr/branding.py to the new position of the JT- ball"
        )


def write_favicons(logo: Path, out_dir: Path) -> None:
    """Write ``favicon.ico`` and ``apple-touch-icon.png`` derived from ``logo``."""
    if not logo.is_file():
        raise BrandingError(f"logo not found at {logo}")

    image = Image.open(logo).convert("RGBA")
    crop = image.crop(_BALL_BOX)
    _assert_is_the_ball(crop, logo)

    # Flatten onto white: .ico transparency renders inconsistently across
    # browsers, and the mark is designed against a white ground anyway.
    flat = Image.new("RGBA", crop.size, (255, 255, 255, 255))
    flat.alpha_composite(crop)
    flat = flat.convert("RGB")

    flat.save(out_dir / "favicon.ico", format="ICO", sizes=_ICO_SIZES)
    flat.resize((_TOUCH_ICON_SIZE, _TOUCH_ICON_SIZE), Image.LANCZOS).save(
        out_dir / "apple-touch-icon.png", format="PNG"
    )
