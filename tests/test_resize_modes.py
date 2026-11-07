import pytest
from PIL import Image

from imgpipe.errors import ConfigError
from imgpipe.steps import create_step
from imgpipe.steps.resize import Resize

RED, GREEN, BLUE = (255, 0, 0), (0, 255, 0), (0, 0, 255)


def solid(size, color=RED, mode="RGB"):
    return Image.new(mode, size, color)


def bands(size=(100, 20)):
    """Red | green | blue vertical bands (30% / 40% / 30% of the width)."""
    image = Image.new("RGB", size)
    w, h = size
    image.paste(RED, (0, 0, w * 3 // 10, h))
    image.paste(GREEN, (w * 3 // 10, 0, w * 7 // 10, h))
    image.paste(BLUE, (w * 7 // 10, 0, w, h))
    return image


# ---------- padding ----------

@pytest.mark.parametrize("size", [(200, 100), (100, 200), (50, 50)])
def test_padding_gives_exact_square(ctx, size):
    result = Resize(mode="padding", size=100).apply(solid(size), ctx)
    assert result.size == (100, 100)


def test_padding_width_and_height(ctx):
    result = Resize(mode="padding", width=120, height=60).apply(solid((200, 200)), ctx)
    assert result.size == (120, 60)


def test_padding_scales_down_and_centers(ctx):
    result = Resize(mode="padding", size=100, fill="white").apply(solid((200, 100)), ctx)
    assert result.getpixel((50, 50)) == RED
    assert result.getpixel((50, 25)) == RED
    assert result.getpixel((50, 24)) == (255, 255, 255)
    assert result.getpixel((50, 74)) == RED
    assert result.getpixel((50, 75)) == (255, 255, 255)


def test_padding_default_fill_is_transparent(ctx):
    result = Resize(mode="padding", size=100).apply(solid((200, 100)), ctx)
    assert result.mode == "RGBA"
    assert result.getpixel((50, 10))[3] == 0
    assert result.getpixel((50, 50)) == RED + (255,)


def test_padding_opaque_fill_on_rgb_gives_rgb(ctx):
    result = Resize(mode="padding", size=100, fill="white").apply(solid((200, 100)), ctx)
    assert result.mode == "RGB"


@pytest.mark.parametrize("fill", ["#ff0000", "red", "#FF0000"])
def test_padding_color_formats(ctx, fill):
    result = Resize(mode="padding", size=100, fill=fill).apply(solid((200, 100), BLUE), ctx)
    assert result.getpixel((50, 5)) == RED


def test_padding_fill_with_alpha(ctx):
    result = Resize(mode="padding", size=100, fill="#ff000080").apply(solid((200, 100)), ctx)
    assert result.mode == "RGBA"
    assert result.getpixel((50, 5)) == RED + (128,)


def test_padding_small_image_keeps_size_and_is_centered(ctx):
    result = Resize(mode="padding", size=100, fill="white").apply(solid((40, 20)), ctx)
    assert result.size == (100, 100)
    assert result.getpixel((30, 40)) == RED
    assert result.getpixel((69, 59)) == RED
    assert result.getpixel((29, 40)) == (255, 255, 255)
    assert result.getpixel((70, 59)) == (255, 255, 255)


def test_padding_small_image_scaled_with_upscale(ctx):
    result = Resize(mode="padding", size=100, fill="white", upscale=True).apply(solid((40, 20)), ctx)
    assert result.getpixel((50, 50)) == RED
    assert result.getpixel((1, 26)) == RED  # spans the full width
    assert result.getpixel((50, 24)) == (255, 255, 255)


def test_padding_exact_size_unchanged(ctx):
    image = solid((100, 100))
    assert Resize(mode="padding", size=100).apply(image, ctx) is image


def test_padding_keeps_semi_transparent_pixels(ctx):
    image = solid((10, 10), (10, 20, 30, 128), mode="RGBA")
    result = Resize(mode="padding", size=20).apply(image, ctx)
    assert result.getpixel((10, 10)) == (10, 20, 30, 128)
    assert result.getpixel((0, 0))[3] == 0


def test_padding_source_with_alpha_over_opaque_fill(ctx):
    image = solid((10, 10), (0, 0, 0, 0), mode="RGBA")
    result = Resize(mode="padding", size=20, fill="white").apply(image, ctx)
    assert result.mode == "RGBA"
    assert result.getpixel((10, 10)) == (255, 255, 255, 255)


def test_padding_grayscale_and_palette_inputs(ctx):
    step = Resize(mode="padding", size=20, fill="white")
    assert step.apply(solid((10, 5), 100, mode="L"), ctx).size == (20, 20)
    assert step.apply(Image.new("P", (10, 5)), ctx).size == (20, 20)


def test_padding_extreme_ratio_keeps_one_pixel(ctx):
    result = Resize(mode="padding", size=100).apply(solid((5000, 3)), ctx)
    assert result.size == (100, 100)


# ---------- crop ----------

@pytest.mark.parametrize("size", [(100, 20), (20, 100), (60, 60)])
def test_crop_gives_exact_square(ctx, size):
    assert Resize(mode="crop", size=10).apply(solid(size), ctx).size == (10, 10)


def test_crop_non_square_target(ctx):
    result = Resize(mode="crop", width=20, height=10).apply(solid((100, 100)), ctx)
    assert result.size == (20, 10)


def test_crop_keeps_the_center_of_a_wide_image(ctx):
    result = Resize(mode="crop", size=10).apply(bands((100, 20)), ctx)
    for x, y in [(0, 0), (5, 5), (9, 9), (0, 9), (9, 0)]:
        r, g, b = result.getpixel((x, y))
        assert g > 200 and r < 60 and b < 60


def test_crop_keeps_the_center_of_a_tall_image(ctx):
    tall = bands((100, 20)).rotate(90, expand=True)  # bands now stacked vertically
    result = Resize(mode="crop", size=10).apply(tall, ctx)
    r, g, b = result.getpixel((5, 5))
    assert g > 200 and r < 60 and b < 60


@pytest.mark.parametrize("size", [(8, 8), (8, 20), (20, 8)])
def test_crop_smaller_image_unchanged_without_upscale(ctx, size):
    image = solid(size)
    assert Resize(mode="crop", size=10).apply(image, ctx) is image


def test_crop_smaller_image_enlarged_with_upscale(ctx):
    result = Resize(mode="crop", size=10, upscale=True).apply(solid((8, 20)), ctx)
    assert result.size == (10, 10)


def test_crop_exact_size_unchanged(ctx):
    image = solid((10, 10))
    assert Resize(mode="crop", size=10).apply(image, ctx) is image


def test_crop_one_dimension_already_exact(ctx):
    result = Resize(mode="crop", size=10).apply(solid((10, 30)), ctx)
    assert result.size == (10, 10)


def test_crop_keeps_transparency(ctx):
    result = Resize(mode="crop", size=10).apply(solid((40, 20), (1, 2, 3, 0), mode="RGBA"), ctx)
    assert result.mode == "RGBA" and result.getpixel((5, 5))[3] == 0


# ---------- validation ----------

@pytest.mark.parametrize(
    "options, message",
    [
        ({"mode": "padding"}, "needs 'size' or both 'width' and 'height'"),
        ({"mode": "padding", "width": 10}, "needs 'size' or both"),
        ({"mode": "crop", "height": 10}, "needs 'size' or both"),
        ({"mode": "padding", "size": 10, "width": 10, "height": 10}, "either 'size' or"),
        ({"mode": "crop", "size": 10, "height": 10}, "either 'size' or"),
        ({"size": 10, "width": 5}, "'width' is not used by mode 'longest_side'"),
        ({"size": 10, "height": 5}, "'height' is not used by mode 'longest_side'"),
        ({"size": 10, "fill": "white"}, "'fill' is not used by mode 'longest_side'"),
        ({"mode": "crop", "size": 10, "fill": "white"}, "'fill' is not used by mode 'crop'"),
        ({"mode": "padding", "size": 10, "fill": "nope"}, "invalid fill color"),
        ({"mode": "padding", "size": 10, "fill": "#12"}, "invalid fill color"),
        ({"mode": "spin", "size": 10}, "unknown mode 'spin'; known modes: longest_side, padding, crop"),
        ({"mode": "padding", "width": 0, "height": 10}, "'width' must be at least 1"),
        ({"mode": "crop", "width": 10, "height": -5}, "'height' must be at least 1"),
        ({"mode": "padding", "size": 0}, "'size' must be at least 1"),
        ({"mode": "padding", "width": "10", "height": 10}, "option 'width' must be int"),
        ({"mode": "padding", "size": True}, "option 'size' must be int"),
        ({"mode": "padding", "size": 10, "fill": 5}, "option 'fill' must be str"),
    ],
)
def test_invalid_options_rejected(options, message):
    with pytest.raises(ConfigError, match=f"step 'resize'.*{message}"):
        create_step("resize", options)


def test_square_shorthand_sets_width_and_height():
    step = create_step("resize", {"mode": "crop", "size": 7})
    assert (step.width, step.height) == (7, 7)


def test_longest_side_without_size_reports_missing_option():
    with pytest.raises(ConfigError, match="missing required option 'size'"):
        create_step("resize", {})
