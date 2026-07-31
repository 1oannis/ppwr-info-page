"""Derive the favicon from the company logo.

The logo is the single source of truth for the brand: the icons are the orange
"JT-" ball at its left edge, masked out at build time rather than maintained as
separate images that could drift out of sync.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

# The ball in `site/static/logo.png` (480x213), fitted from the logo's own
# pixels: centroid of the warm-coloured region, and the radius at which that
# region ends. `_assert_is_the_ball` fails the build if a replacement logo
# moves the mark, rather than silently shipping an icon of empty space.
_BALL_CENTRE = (103.5, 108.5)
_BALL_RADIUS = 59

# Antialias the circular mask by drawing it large and shrinking it, otherwise
# the ball gets a visibly stair-stepped edge at icon sizes.
_MASK_OVERSAMPLE = 8

# Sizes browsers actually request: 16/32 for the tab, 48 for Windows taskbar
# pins, 180 for an iOS home-screen bookmark.
_ICO_SIZES = ((16, 16), (32, 32), (48, 48))
_TOUCH_ICON_SIZE = 180


class BrandingError(Exception):
    """The logo is missing or does not look like the logo we expect."""


def _is_ball(pixel: tuple[int, int, int, int]) -> bool:
    """Warm and opaque: the orange ball, but not the grey swoosh behind it."""
    red, green, blue, alpha = pixel
    return alpha > 100 and red > 140 and (red - blue) > 45


def _crop_box() -> tuple[int, int, int, int]:
    centre_x, centre_y = _BALL_CENTRE
    return (
        round(centre_x - _BALL_RADIUS),
        round(centre_y - _BALL_RADIUS),
        round(centre_x + _BALL_RADIUS),
        round(centre_y + _BALL_RADIUS),
    )


def _circular_mask(size: tuple[int, int]) -> Image.Image:
    width, height = size
    big = Image.new("L", (width * _MASK_OVERSAMPLE, height * _MASK_OVERSAMPLE), 0)
    ImageDraw.Draw(big).ellipse((0, 0, big.width - 1, big.height - 1), fill=255)
    return big.resize(size, Image.LANCZOS)


def _assert_is_the_ball(crop: Image.Image, source: Path) -> None:
    pixels = crop.load()
    width, height = crop.size
    ball = sum(
        1
        for y in range(height)
        for x in range(width)
        if _is_ball(pixels[x, y])
    )
    # A disc inscribed in its bounding square covers pi/4 ~ 79% of it. Well
    # under that means the crop is not centred on the ball any more.
    share = ball / (width * height)
    if share < 0.55:
        raise BrandingError(
            f"{source.name}: only {share:.0%} of the crop at centre {_BALL_CENTRE} "
            f"radius {_BALL_RADIUS} is the orange ball, so the logo has probably "
            "changed - refit _BALL_CENTRE and _BALL_RADIUS in ppwr/branding.py"
        )


def _ball_icon(logo: Path) -> Image.Image:
    """The ball cropped to a square and masked to a circle, on transparency."""
    if not logo.is_file():
        raise BrandingError(f"logo not found at {logo}")

    image = Image.open(logo).convert("RGBA")
    crop = image.crop(_crop_box())
    _assert_is_the_ball(crop, logo)

    # Intersect the circle with the logo's own alpha - per-pixel minimum - so
    # the ball keeps its soft edge and everything outside the circle (the grey
    # swoosh passing behind it) drops away.
    alpha = ImageChops.darker(crop.getchannel("A"), _circular_mask(crop.size))
    ball = crop.copy()
    ball.putalpha(alpha)
    return ball


def write_favicons(logo: Path, out_dir: Path) -> None:
    """Write ``favicon.ico`` and ``apple-touch-icon.png`` derived from ``logo``."""
    ball = _ball_icon(logo)

    ball.save(out_dir / "favicon.ico", format="ICO", sizes=_ICO_SIZES)

    # iOS composites a transparent home-screen icon onto black, which would
    # frame the ball in a black square. Give this one a white ground; the
    # browser-tab favicon above keeps its transparency.
    touch = Image.new("RGBA", ball.size, (255, 255, 255, 255))
    touch.alpha_composite(ball)
    touch.convert("RGB").resize(
        (_TOUCH_ICON_SIZE, _TOUCH_ICON_SIZE), Image.LANCZOS
    ).save(out_dir / "apple-touch-icon.png", format="PNG")
