from dataclasses import dataclass

from PIL import Image

from imgpipe.colors import TRANSPARENT, parse_color
from imgpipe.steps import Context, Step, normalize_mode, register

MODES = ("longest_side", "scale", "padding", "crop")


@register("resize")
@dataclass
class Resize(Step):
    """Scale keeping proportions.

    ``longest_side``: the longer side becomes ``size``.
    ``scale``: ``width`` or ``height`` (exactly one) is set, the other side follows.
    ``padding``: fit inside ``width`` x ``height`` (or ``size`` x ``size``), fill the rest.
    ``crop``: cover ``width`` x ``height`` completely, center-crop the overflow.
    Images smaller than the target are enlarged unless ``upscale`` is false.
    """

    mode: str = "longest_side"
    size: int | None = None
    width: int | None = None
    height: int | None = None
    upscale: bool = True
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

        if self.mode == "scale":
            if (self.width is None) == (self.height is None):
                raise ValueError("mode 'scale' needs exactly one of 'width' and 'height'")
            for name in ("size", "fill"):
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
            self._fill_color = parse_color(self.fill or "transparent", what="fill color")

    # The result size is computed from the input size alone, not from the pixels.
    depends_on_pixels = False
    depends_on_size = True

    def _output_size(self, size: tuple[int, int], swap: bool = False) -> tuple[int, int]:
        """The size this step produces for an input of ``size``.

        With ``swap`` the stored image is shown with its axes exchanged (EXIF orientation
        kept): ``width`` and ``height`` then refer to the shown photo.
        """
        if swap:
            return self._shown_output_size(size[::-1])[::-1]
        return self._shown_output_size(size)

    def _shown_output_size(self, size: tuple[int, int]) -> tuple[int, int]:
        w, h = size
        if self.mode == "longest_side":
            longest = max(w, h)
            if longest == self.size or (longest < self.size and not self.upscale):
                return size
            scale = self.size / longest
            width, height = (max(1, round(side * scale)) for side in size)
            if w >= h:
                width = self.size
            else:
                height = self.size
            return width, height
        if self.mode == "scale":
            if self.width is not None:
                target = (self.width, max(1, round(h * self.width / w)))
            else:
                target = (max(1, round(w * self.height / h)), self.height)
            if not self.upscale and (target[0] > w or target[1] > h):
                return size
            return target
        if self.mode == "crop" and not self.upscale and (w < self.width or h < self.height):
            return size  # too small to cover the target; left as it is
        return self.width, self.height

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        swap = ctx.swaps_axes
        target = self._output_size(image.size, swap)
        if target == image.size:
            return image
        if ctx.skip_pixels:
            # Dry run: no later step needs the pixels.
            if ctx.skip_resize:
                ctx.record_size(target)  # nor the size: just report it
                return image
            return Image.new(image.mode, target)  # a blank image of the right size
        if self.mode in ("longest_side", "scale"):
            return normalize_mode(image).resize(target, Image.Resampling.LANCZOS)
        if self.mode == "padding":
            return self._padding(image, swap)
        return self._crop(image, swap)

    def _target(self, swap: bool) -> tuple[int, int]:
        return (self.height, self.width) if swap else (self.width, self.height)

    def _padding(self, image: Image.Image, swap: bool = False) -> Image.Image:
        target = self._target(swap)
        width, height = target
        image = normalize_mode(image)
        scale = min(width / image.width, height / image.height)
        if scale != 1 and (scale < 1 or self.upscale):
            new_size = (
                min(width, max(1, round(image.width * scale))),
                min(height, max(1, round(image.height * scale))),
            )
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        # Paste unblended on a transparent layer first so semi-transparent pixels keep
        # their alpha, then composite the layer over the fill.
        layer = Image.new("RGBA", target, TRANSPARENT)
        layer.paste(
            image.convert("RGBA"),
            ((width - image.width) // 2, (height - image.height) // 2),
        )
        result = Image.alpha_composite(Image.new("RGBA", target, self._fill_color), layer)
        if self._fill_color[3] < 255 or image.mode in ("RGBA", "LA"):
            return result
        return result.convert("RGB")

    def _crop(self, image: Image.Image, swap: bool = False) -> Image.Image:
        width, height = self._target(swap)
        scale = max(width / image.width, height / image.height)
        if scale != 1:
            new_size = (
                max(width, round(image.width * scale)),
                max(height, round(image.height * scale)),
            )
            image = normalize_mode(image).resize(new_size, Image.Resampling.LANCZOS)
        left = (image.width - width) // 2
        top = (image.height - height) // 2
        return image.crop((left, top, left + width, top + height))
