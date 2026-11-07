from dataclasses import dataclass

from PIL import Image

from imgpipe.steps import Context, Step, normalize_mode, register

MODES = ("longest_side",)


@register("resize")
@dataclass
class Resize(Step):
    """Scale keeping proportions. ``longest_side``: the longer side becomes ``size``."""

    size: int
    mode: str = "longest_side"
    upscale: bool = False

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown mode '{self.mode}'; known modes: {', '.join(MODES)}")
        if self.size < 1:
            raise ValueError(f"'size' must be at least 1, got {self.size}")

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        longest = max(image.size)
        if longest == self.size or (longest < self.size and not self.upscale):
            return image
        scale = self.size / longest
        width, height = (max(1, round(side * scale)) for side in image.size)
        if image.width >= image.height:
            width = self.size
        else:
            height = self.size
        return normalize_mode(image).resize((width, height), Image.Resampling.LANCZOS)
