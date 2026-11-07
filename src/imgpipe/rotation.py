"""Rotation shared by the `rotate` and `rnd_rotate` steps.

Angles are in degrees and positive means clockwise (Pillow turns counterclockwise, so the
sign is flipped when calling it). This module does not import the steps package.
"""

import math

from PIL import Image

from imgpipe.colors import parse_color

CORNERS = ("crop", "fill")
RESAMPLE = Image.Resampling.BICUBIC
# Clockwise quarter turns -> the lossless transpose that does it.
QUARTER_TURNS = {
    1: Image.Transpose.ROTATE_270,
    2: Image.Transpose.ROTATE_180,
    3: Image.Transpose.ROTATE_90,
}


def check_corners(corners: str, fill: str | None) -> tuple[int, int, int, int] | None:
    """Validate the `corners` / `fill` options; returns the fill color (None for `crop`)."""
    if corners not in CORNERS:
        raise ValueError(f"unknown corners '{corners}'; known values: {', '.join(CORNERS)}")
    if corners == "crop":
        if fill is not None:
            raise ValueError(f"option 'fill' is not used by corners '{corners}'")
        return None
    return parse_color(fill or "transparent", what="fill color")


def quarter_turns(angle: float) -> int | None:
    """0-3 clockwise quarter turns if the angle is a multiple of 90 degrees, else ``None``."""
    nearest = round(angle / 90)
    return nearest % 4 if abs(angle - nearest * 90) < 1e-9 else None


def inner_scale(width: int, height: int, angle: float) -> float:
    """How much of the original size the largest centered upright rectangle keeps.

    The rectangle has the original aspect ratio, and fits entirely inside the
    ``width`` x ``height`` rectangle rotated by ``angle``.
    """
    a = math.radians(abs(angle) % 180)
    if a > math.pi / 2:
        a = math.pi - a
    c, s = math.cos(a), math.sin(a)
    return min(width / (width * c + height * s), height / (width * s + height * c))


def rotate_image(
    image: Image.Image, angle: float, corners: str, fill: tuple[int, int, int, int] | None
) -> Image.Image:
    """Rotate an image (mode L, LA, RGB or RGBA) clockwise by ``angle`` degrees.

    ``corners = "crop"``: the empty corners are cut away (the largest centered rectangle
    with the original aspect ratio). ``corners = "fill"``: the canvas grows to hold the
    whole image and the corners get ``fill`` (an RGBA color). Multiples of 90 degrees are
    exact turns with no corners; a multiple of 360 returns the image itself.
    """
    turns = quarter_turns(angle)
    if turns == 0:
        return image
    if turns is not None:
        return image.transpose(QUARTER_TURNS[turns])
    if corners == "crop":
        return _rotate_and_crop(image, angle)
    return _rotate_and_fill(image, angle, fill)


def _rotate_pixels(image: Image.Image, angle: float, fillcolor=None) -> Image.Image:
    """Rotate with an enlarged canvas, keeping the mode (the corners are `fillcolor` or black/transparent)."""
    if image.mode in ("RGBA", "LA"):
        # Premultiplied alpha: soft edges and transparent areas do not darken their neighbors.
        rotated = image.convert("RGBA").convert("RGBa").rotate(-angle, resample=RESAMPLE, expand=True)
        return rotated.convert("RGBA").convert(image.mode)
    return image.rotate(-angle, resample=RESAMPLE, expand=True, fillcolor=fillcolor)


def _rotate_and_crop(image: Image.Image, angle: float) -> Image.Image:
    width, height = image.size
    rotated = _rotate_pixels(image, angle)
    scale = inner_scale(width, height, angle)
    # One pixel less on each side: no pixel that was blended with the empty corners remains.
    new_width = max(1, int(width * scale) - 2)
    new_height = max(1, int(height * scale) - 2)
    left = (rotated.width - new_width) // 2
    top = (rotated.height - new_height) // 2
    return rotated.crop((left, top, left + new_width, top + new_height))


def _rotate_and_fill(image: Image.Image, angle: float, fill: tuple[int, int, int, int]) -> Image.Image:
    has_alpha = image.mode in ("RGBA", "LA")
    if not has_alpha and fill[3] == 255:
        # Plain case: rotate in the image's own mode with the fill color. A gray image
        # becomes RGB unless the fill is gray too.
        gray_fill = fill[0] == fill[1] == fill[2]
        base = image.convert("RGB") if image.mode == "L" and not gray_fill else image
        return _rotate_pixels(base, angle, fill[0] if base.mode == "L" else fill[:3])

    rotated = _rotate_pixels(image.convert("RGBA"), angle)
    if fill[3] == 0:
        return rotated
    # Paint the fill only outside the rotated picture; transparency inside stays as it was.
    footprint = Image.new("L", image.size, 255).rotate(-angle, resample=RESAMPLE, expand=True)
    alpha = footprint.point(lambda inside: round(fill[3] * (255 - inside) / 255))
    layer = Image.new("RGBA", rotated.size, fill[:3] + (255,))
    layer.putalpha(alpha)
    return Image.alpha_composite(layer, rotated)
