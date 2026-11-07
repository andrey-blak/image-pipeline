import math
from dataclasses import dataclass

from PIL import Image

from imgpipe.rotation import check_corners, quarter_turns, rotate_image
from imgpipe.steps import Context, Step, normalize_mode, register


@register("rotate")
@dataclass
class Rotate(Step):
    """Rotate by a fixed angle (degrees, positive = clockwise).

    ``corners``: ``crop`` cuts away the empty corners, ``fill`` keeps everything on a larger
    canvas and fills the corners with ``fill`` (default transparent). Multiples of 90 degrees
    are exact turns.
    """

    angle: float
    corners: str = "crop"
    fill: str | None = None

    # Keeps the default `depends_on_*` flags: the step always runs, also in a dry run.

    def __post_init__(self):
        if not math.isfinite(self.angle):
            raise ValueError(f"'angle' must be a finite number, got {self.angle}")
        self._fill = check_corners(self.corners, self.fill)

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        if quarter_turns(self.angle) == 0:
            return image  # a full turn: nothing to do
        ctx.record("rotation", f"{self.angle:+g}°")
        return rotate_image(normalize_mode(image), self.angle, self.corners, self._fill)
