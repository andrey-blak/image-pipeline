import colorsys
import random
import re

import pytest
from PIL import Image

from imgpipe.steps import Context
from imgpipe.steps.rnd_saturation import RandomSaturation


def saturation_of(image):
    r, g, b = (v / 255 for v in image.convert("RGB").getpixel((0, 0)))
    return colorsys.rgb_to_hsv(r, g, b)[1]


def chroma_of(image):
    return max(image.getpixel((0, 0))[:3]) - min(image.getpixel((0, 0))[:3])


def solid(color=(150, 110, 90), mode="RGB", size=(4, 4)):
    return Image.new(mode, size, color)


def test_random_saturation_increases(ctx):
    image = solid()
    result = RandomSaturation(min_percent=50, max_percent=50).apply(image, ctx)
    assert saturation_of(result) > saturation_of(image)


def test_negative_percent_decreases(ctx):
    image = solid()
    result = RandomSaturation(min_percent=-50, max_percent=-50).apply(image, ctx)
    assert saturation_of(result) < saturation_of(image)


def test_zero_percent_is_identity(ctx):
    image = solid()
    result = RandomSaturation(min_percent=0, max_percent=0).apply(image, ctx)
    assert result.tobytes() == image.tobytes()


def test_percent_drawn_within_range_and_differs_per_image(ctx):
    step = RandomSaturation(min_percent=3, max_percent=5)
    color = (200, 100, 20)  # high chroma, so 8-bit rounding stays small
    base = chroma_of(solid(color))
    ratios = {chroma_of(step.apply(solid(color), ctx)) / base for _ in range(30)}
    assert len(ratios) > 1
    # Chroma scales by the factor; allow for 8-bit rounding around 1.03..1.05.
    assert all(1.02 < r < 1.06 for r in ratios)


def test_same_seed_gives_same_result():
    step = RandomSaturation(min_percent=3, max_percent=40)
    results = [
        step.apply(solid(), Context(rng=random.Random(7))).tobytes() for _ in range(2)
    ]
    assert results[0] == results[1]


def test_alpha_channel_preserved(ctx):
    image = solid((150, 110, 90, 77), mode="RGBA")
    result = RandomSaturation(min_percent=50, max_percent=50).apply(image, ctx)
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 77


def test_grayscale_unchanged(ctx):
    image = solid(100, mode="L")
    result = RandomSaturation(min_percent=50, max_percent=50).apply(image, ctx)
    assert result.tobytes() == image.tobytes()


def test_palette_image_is_handled(ctx):
    result = RandomSaturation(min_percent=10, max_percent=10).apply(Image.new("P", (4, 4)), ctx)
    assert result.mode == "RGB"


def test_min_above_max_rejected():
    with pytest.raises(ValueError, match="must not exceed"):
        RandomSaturation(min_percent=5, max_percent=3)


def test_percent_below_minus_100_rejected():
    with pytest.raises(ValueError, match="above -100"):
        RandomSaturation(min_percent=-100, max_percent=0)


def test_applied_percent_is_recorded(ctx):
    RandomSaturation(min_percent=3, max_percent=5).apply(solid(), ctx)
    assert list(ctx.changes) == ["saturation"]
    assert re.fullmatch(r"\+[345]\.\d%", ctx.changes["saturation"])
    assert 3 <= float(ctx.changes["saturation"].rstrip("%")) <= 5


def test_negative_percent_recorded_with_sign(ctx):
    RandomSaturation(min_percent=-20, max_percent=-20).apply(solid(), ctx)
    assert ctx.changes == {"saturation": "-20.0%"}


def test_grayscale_recorded_as_not_applicable(ctx):
    RandomSaturation(min_percent=10, max_percent=10).apply(solid(100, mode="L"), ctx)
    assert ctx.changes == {"saturation": "n/a (grayscale)"}
