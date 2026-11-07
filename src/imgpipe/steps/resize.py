from dataclasses import dataclass

from PIL import Image, ImageColor

from imgpipe.steps import Context, Step, normalize_mode, register

MODES = ("longest_side", "padding", "crop")
TRANSPARENT = (0, 0, 0, 0)


def _parse_fill(value: str) -> tuple[int, int, int, int]:
    if value == "transparent":
        return TRANSPARENT
    try:
        return ImageColor.getcolor(value, "RGBA")
    except ValueError:
        raise ValueError(
            f"invalid fill color {value!r}; use 'transparent', a name like 'white', "
            "or hex like '#ffffff'"
        ) from None


@register("resize")
@dataclass
class Resize(Step):
    """Scale keeping proportions.

    ``longest_side``: the longer side becomes ``size``.
    ``padding``: fit inside ``width`` x ``height`` (or ``size`` x ``size``), fill the rest.
    ``crop``: cover ``width`` x ``height`` completely, center-crop the overflow.
    Images smaller than the target are enlarged only with ``upscale``.
    """

    mode: str = "longest_side"
    size: int | None = None
    width: int | None = None
    height: int | None = None
    upscale: bool = False
    fill: str | None = None

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown mode '{self.mode}'; known modes: {', '.join(MODES)}")
        for name in ("size", "width", "height"):
            value = getattr(self, name)
            if value is not None and value < 1:
                raise ValueError(f"'{name}' must be at least 1, got {value}")

        if self.mode == "longest_side":
            if self.size is None:
                raise ValueError("missing required option 'size'")
            for name in ("width", "height", "fill"):
                if getattr(self, name) is not None:
                    raise ValueError(f"option '{name}' is not used by mode '{self.mode}'")
            return

        if self.size is not None and (self.width is not None or self.height is not None):
            raise ValueError("use either 'size' or 'width' and 'height', not both")
        if self.size is not None:
            self.width = self.height = self.size
        elif self.width is None or self.height is None:
            raise ValueError(f"mode '{self.mode}' needs 'size' or both 'width' and 'height'")
        if self.mode == "crop" and self.fill is not None:
            raise ValueError(f"option 'fill' is not used by mode '{self.mode}'")
        if self.mode == "padding":
            self._fill_color = _parse_fill(self.fill or "transparent")

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        if self.mode == "longest_side":
            return self._longest_side(image)
        if image.size == (self.width, self.height):
            return image
        if self.mode == "padding":
            return self._padding(image)
        return self._crop(image)

    def _longest_side(self, image: Image.Image) -> Image.Image:
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

    def _padding(self, image: Image.Image) -> Image.Image:
        target = (self.width, self.height)
        image = normalize_mode(image)
        scale = min(self.width / image.width, self.height / image.height)
        if scale != 1 and (scale < 1 or self.upscale):
            new_size = (
                min(self.width, max(1, round(image.width * scale))),
                min(self.height, max(1, round(image.height * scale))),
            )
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        # Paste unblended on a transparent layer first so semi-transparent pixels keep
        # their alpha, then composite the layer over the fill.
        layer = Image.new("RGBA", target, TRANSPARENT)
        layer.paste(
            image.convert("RGBA"),
            ((self.width - image.width) // 2, (self.height - image.height) // 2),
        )
        result = Image.alpha_composite(Image.new("RGBA", target, self._fill_color), layer)
        if self._fill_color[3] < 255 or image.mode in ("RGBA", "LA"):
            return result
        return result.convert("RGB")

    def _crop(self, image: Image.Image) -> Image.Image:
        if not self.upscale and (image.width < self.width or image.height < self.height):
            return image
        scale = max(self.width / image.width, self.height / image.height)
        if scale != 1:
            new_size = (
                max(self.width, round(image.width * scale)),
                max(self.height, round(image.height * scale)),
            )
            image = normalize_mode(image).resize(new_size, Image.Resampling.LANCZOS)
        left = (image.width - self.width) // 2
        top = (image.height - self.height) // 2
        return image.crop((left, top, left + self.width, top + self.height))
