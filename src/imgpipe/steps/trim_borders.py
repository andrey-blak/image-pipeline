from dataclasses import dataclass
from itertools import combinations

from PIL import Image, ImageChops

from imgpipe.colors import TRANSPARENT, parse_color
from imgpipe.steps import Context, Step, normalize_mode, register


@register("trim_borders")
@dataclass
class TrimBorders(Step):
    """Cut off solid-color or transparent margins around the content.

    ``background``: ``auto`` (the four corners must be the same color, otherwise nothing is
    cut), ``transparent``, or a color. ``tolerance``: how far (0-255) colors may differ and
    still count as the same: the corners from each other (``auto``) and a pixel from the
    background. The default 0 means exact.
    """

    background: str = "auto"
    tolerance: int = 0

    # Depends on the pixels (the result size comes from them) and never skips its work
    # in a dry run, so it keeps the default `depends_on_*` flags.

    def __post_init__(self):
        if not 0 <= self.tolerance <= 255:
            raise ValueError(f"'tolerance' must be between 0 and 255, got {self.tolerance}")
        self._color = None if self.background == "auto" else parse_color(
            self.background, what="background color"
        )

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        original = image
        image = normalize_mode(image)
        rgba = image.convert("RGBA")
        background = self._color if self._color is not None else _background_from_corners(rgba, self.tolerance)
        if background is None:
            return original  # no uniform border to find
        box = _content_box(rgba, background, self.tolerance)
        width, height = image.size
        if box is None or box == (0, 0, width, height):
            return original  # all background, or nothing to cut
        left, top, right, bottom = box
        ctx.record("trim", f"L{left} T{top} R{width - right} B{height - bottom}")
        return image.crop(box)


def _background_from_corners(
    rgba: Image.Image, tolerance: int
) -> tuple[int, int, int, int] | None:
    """The background color shared by the four corners, or ``None`` if they do not agree.

    Corners agree when no two of them differ by more than ``tolerance`` in any channel
    (alpha included). If every corner is transparent (alpha not above ``tolerance``) the
    background is "transparent", whatever the hidden RGB values. Otherwise the top-left
    corner is the background color.
    """
    width, height = rgba.size
    corners = [
        rgba.getpixel(xy)
        for xy in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    ]
    if all(corner[3] <= tolerance for corner in corners):
        return TRANSPARENT
    for first, second in combinations(corners, 2):
        if max(abs(a - b) for a, b in zip(first, second)) > tolerance:
            return None
    return corners[0]


def _content_box(
    rgba: Image.Image, background: tuple[int, int, int, int], tolerance: int
) -> tuple[int, int, int, int] | None:
    """Bounding box of the pixels that differ from the background by more than ``tolerance``."""
    if background[3] == 0:
        return rgba.getchannel("A").point(lambda a: 255 if a > tolerance else 0).getbbox()
    solid = background[:3]
    # Transparent areas count as the background color.
    flat = Image.alpha_composite(Image.new("RGBA", rgba.size, solid + (255,)), rgba).convert("RGB")
    diff = ImageChops.difference(flat, Image.new("RGB", rgba.size, solid))
    red, green, blue = diff.point(lambda d: 255 if d > tolerance else 0).split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue).getbbox()
