from dataclasses import dataclass

from PIL import Image

from imgpipe.rotation import check_corners, quarter_turns, rotate_image
from imgpipe.steps import Context, Step, normalize_mode, register


@register("rnd_rotate")
@dataclass
class RandomRotate(Step):
    """Rotate by a random angle, drawn per image.

    The angle is between ``min_angle`` and ``max_angle`` degrees (both absolute values); the
    direction, clockwise or counterclockwise, is chosen at random. ``corners`` and ``fill``
    work as in ``rotate``.
    """

    min_angle: float = 0
    max_angle: float = 5
    corners: str = "crop"
    fill: str | None = None

    # Keeps the default `depends_on_*` flags: the step always runs, also in a dry run.

    def __post_init__(self):
        if not 0 <= self.min_angle <= self.max_angle <= 180:
            raise ValueError(
                "angles must satisfy 0 <= min_angle <= max_angle <= 180, "
                f"got min_angle = {self.min_angle}, max_angle = {self.max_angle}"
            )
        self._fill = check_corners(self.corners, self.fill)

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        magnitude = ctx.rng.uniform(self.min_angle, self.max_angle)
        angle = magnitude if ctx.rng.random() < 0.5 else -magnitude
        if quarter_turns(angle) == 0:
            return image  # 0 degrees: nothing to do
        ctx.record("rotation", f"{angle:+.1f}°")
        shown = -angle if ctx.mirrored else angle  # as the photo is shown
        return rotate_image(normalize_mode(image), shown, self.corners, self._fill)
