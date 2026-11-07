from dataclasses import dataclass

from PIL import Image, ImageEnhance

from imgpipe.steps import Context, Step, normalize_mode, register


@register("rnd_saturation")
@dataclass
class RandomSaturation(Step):
    """Change saturation by a random percent in [min_percent, max_percent], drawn per image."""

    min_percent: float
    max_percent: float

    def __post_init__(self):
        if self.min_percent > self.max_percent:
            raise ValueError(
                f"'min_percent' ({self.min_percent}) must not exceed "
                f"'max_percent' ({self.max_percent})"
            )
        if self.min_percent <= -100:
            raise ValueError(f"'min_percent' must be above -100, got {self.min_percent}")

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        percent = ctx.rng.uniform(self.min_percent, self.max_percent)
        image = normalize_mode(image)
        if image.mode in ("L", "LA"):
            return image  # no color to saturate
        factor = 1 + percent / 100
        if image.mode == "RGBA":
            # Enhancing RGBA directly would distort the alpha channel.
            result = ImageEnhance.Color(image.convert("RGB")).enhance(factor)
            result.putalpha(image.getchannel("A"))
            return result
        return ImageEnhance.Color(image).enhance(factor)
