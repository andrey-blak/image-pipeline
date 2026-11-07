from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageStat

from imgpipe.steps import Context, Step, normalize_mode, register

METHODS = ("autocontrast", "target_mean")
# Option -> (method that uses it, default used when the method is chosen).
OPTIONS = {
    "cutoff": ("autocontrast", 0.5),
    "target": ("target_mean", 128),
    "max_change": ("target_mean", 0.3),
}


@register("auto_brightness")
@dataclass
class AutoBrightness(Step):
    """Adjust brightness automatically.

    ``autocontrast``: levels stretch. The brightest and darkest pixels (ignoring ``cutoff``
    percent of them at each end) are mapped to white and black; the same adjustment is
    applied to every color channel, so colors keep their balance.
    ``target_mean``: scale brightness toward an average of ``target`` (0-255), changing it by
    at most the factor ``1 +/- max_change``.
    """

    method: str = "autocontrast"
    cutoff: float | None = None
    target: int | None = None
    max_change: float | None = None

    # The result and the recorded values come from the pixels, so this step never skips its
    # work in a dry run (`depends_on_pixels` stays True); it does not depend on the size.
    depends_on_size = False

    def __post_init__(self):
        if self.method not in METHODS:
            raise ValueError(f"unknown method '{self.method}'; known methods: {', '.join(METHODS)}")
        for name, (method, default) in OPTIONS.items():
            if getattr(self, name) is None:
                if method == self.method:
                    setattr(self, name, default)
            elif method != self.method:
                raise ValueError(f"option '{name}' is not used by method '{self.method}'")
        if self.cutoff is not None and not 0 <= self.cutoff < 50:
            raise ValueError(f"'cutoff' must be at least 0 and below 50, got {self.cutoff}")
        if self.target is not None and not 0 <= self.target <= 255:
            raise ValueError(f"'target' must be between 0 and 255, got {self.target}")
        if self.max_change is not None and not 0 < self.max_change <= 1:
            raise ValueError(f"'max_change' must be above 0 and at most 1, got {self.max_change}")

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        original = image
        image = normalize_mode(image)
        alpha = image.getchannel("A") if image.mode in ("RGBA", "LA") else None
        base = image.convert("L" if image.mode in ("L", "LA") else "RGB")
        # Fully transparent pixels take no part in the statistics.
        mask = alpha.point(lambda a: 255 if a else 0) if alpha is not None else None
        if mask is not None and mask.getbbox() is None:
            return original  # nothing visible

        if self.method == "autocontrast":
            result = self._autocontrast(base, mask, ctx)
        else:
            result = self._target_mean(base, mask, ctx)
        if result is None:
            return original
        if alpha is not None:
            result.putalpha(alpha)
        return result

    def _autocontrast(self, base: Image.Image, mask: Image.Image | None, ctx: Context):
        low, high = _levels(base.convert("L").histogram(mask), self.cutoff)
        if high <= low or (low, high) == (0, 255):
            return None  # flat image, or already uses the full range
        scale = 255.0 / (high - low)
        offset = -low * scale  # same arithmetic as PIL.ImageOps.autocontrast
        lut = [min(255, max(0, int(level * scale + offset))) for level in range(256)]
        ctx.record("brightness", f"levels {low}-{high} -> 0-255")
        return base.point(lut * len(base.getbands()))

    def _target_mean(self, base: Image.Image, mask: Image.Image | None, ctx: Context):
        mean = ImageStat.Stat(base.convert("L"), mask).mean[0]
        if mean <= 0:
            return None  # black: nothing to scale
        wanted = self.target / mean
        factor = min(1 + self.max_change, max(1 - self.max_change, wanted))
        if round(factor, 2) == 1.0:
            return None
        limited = ", limited" if factor != wanted else ""
        ctx.record("brightness", f"x{factor:.2f} (mean {mean:.0f}, target {self.target}{limited})")
        return ImageEnhance.Brightness(base).enhance(factor)


def _levels(histogram: list[int], cutoff: float) -> tuple[int, int]:
    """Darkest and lightest level left after ignoring ``cutoff`` percent of the pixels at each end.

    Same algorithm as `PIL.ImageOps.autocontrast`. Returns ``(255, 0)`` for an empty histogram.
    """
    counts = list(histogram)
    if cutoff:
        ignored = int(sum(counts) * cutoff // 100)
        _remove_pixels(counts, ignored, range(256))
        _remove_pixels(counts, ignored, range(255, -1, -1))
    low = next((level for level in range(256) if counts[level]), 255)
    high = next((level for level in range(255, -1, -1) if counts[level]), 0)
    return low, high


def _remove_pixels(counts: list[int], amount: int, levels) -> None:
    """Remove ``amount`` pixels from the histogram, walking through ``levels`` in order."""
    for level in levels:
        if amount <= 0:
            break
        if amount > counts[level]:
            amount -= counts[level]
            counts[level] = 0
        else:
            counts[level] -= amount
            amount = 0
