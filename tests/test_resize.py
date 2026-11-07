import pytest
from PIL import Image

from imgpipe.steps.resize import Resize


@pytest.mark.parametrize(
    "size, expected",
    [((600, 300), (300, 150)), ((300, 600), (150, 300)), ((900, 900), (300, 300))],
)
def test_longest_side_keeps_proportions(ctx, size, expected):
    result = Resize(size=300).apply(Image.new("RGB", size), ctx)
    assert result.size == expected


def test_longest_side_is_exact_for_awkward_ratios(ctx):
    assert max(Resize(size=300).apply(Image.new("RGB", (1001, 7)), ctx).size) == 300


def test_extreme_ratio_keeps_at_least_one_pixel(ctx):
    assert Resize(size=100).apply(Image.new("RGB", (5000, 3)), ctx).size == (100, 1)


def test_small_image_not_enlarged_by_default(ctx):
    image = Image.new("RGB", (100, 50))
    assert Resize(size=300).apply(image, ctx).size == (100, 50)


def test_small_image_enlarged_when_upscale_enabled(ctx):
    result = Resize(size=300, upscale=True).apply(Image.new("RGB", (100, 50)), ctx)
    assert result.size == (300, 150)


def test_palette_image_is_converted_for_resampling(ctx):
    result = Resize(size=10).apply(Image.new("P", (40, 20)), ctx)
    assert result.size == (10, 5)
    assert result.mode == "RGB"


def test_transparency_kept(ctx):
    result = Resize(size=10).apply(Image.new("RGBA", (40, 20), (1, 2, 3, 0)), ctx)
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 0


def test_input_image_not_modified(ctx):
    image = Image.new("RGB", (40, 20))
    Resize(size=10).apply(image, ctx)
    assert image.size == (40, 20)
