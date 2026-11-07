import random

import pytest
from PIL import Image

from imgpipe.errors import ConfigError
from imgpipe.pipeline import Pipeline
from imgpipe.steps import Context, create_step
from imgpipe.steps.trim_borders import TrimBorders

WHITE, RED = (255, 255, 255), (200, 30, 30)


def framed(size=(100, 60), box=(12, 8, 72, 28), bg=WHITE, content=RED, mode="RGB"):
    """An image of `bg` with a `content` rectangle in `box` (left, top, right, bottom)."""
    image = Image.new(mode, size, bg)
    image.paste(content, box)
    return image


# ---------- trimming ----------

def test_trims_a_uniform_border_on_all_sides(ctx):
    result = TrimBorders().apply(framed(box=(10, 10, 90, 50)), ctx)
    assert result.size == (80, 40)
    assert result.getpixel((0, 0)) == RED and result.getpixel((79, 39)) == RED
    assert ctx.changes == {"trim": "L10 T10 R10 B10"}


def test_uneven_borders_are_reported_per_side(ctx):
    result = TrimBorders().apply(framed(), ctx)  # content (12, 8)-(72, 28) in 100x60
    assert result.size == (60, 20)
    assert ctx.changes == {"trim": "L12 T8 R28 B32"}


def test_border_on_two_sides_only(ctx):
    image = framed(size=(100, 60), box=(0, 10, 100, 50))  # white bands top and bottom only
    result = TrimBorders().apply(image, ctx)
    assert result.size == (100, 40)
    assert ctx.changes == {"trim": "L0 T10 R0 B10"}


def test_no_border_returns_the_same_image_and_records_nothing(ctx):
    image = Image.new("RGB", (40, 20), RED)
    assert TrimBorders().apply(image, ctx) is image
    assert ctx.changes == {}


def test_all_background_image_is_left_alone(ctx):
    image = Image.new("RGB", (40, 20), WHITE)
    assert TrimBorders().apply(image, ctx) is image
    assert ctx.changes == {}


def test_repeated_trims_are_appended(ctx):
    step = TrimBorders()
    step.apply(framed(box=(10, 10, 90, 50)), ctx)
    step.apply(framed(box=(10, 10, 90, 50)), ctx)
    assert ctx.changes == {"trim": "L10 T10 R10 B10, L10 T10 R10 B10"}


def test_input_image_is_not_modified(ctx):
    image = framed()
    TrimBorders().apply(image, ctx)
    assert image.size == (100, 60)


# ---------- background: auto ----------

def test_auto_needs_all_four_corners_to_agree_exactly(ctx):
    image = framed()
    image.putpixel((0, 0), (254, 254, 254))  # one level off
    assert TrimBorders().apply(image, ctx) is image
    assert ctx.changes == {}


def test_auto_with_a_border_on_one_side_only_leaves_the_image(ctx):
    image = framed(size=(100, 60), box=(20, 0, 100, 60))  # white strip on the left only
    assert TrimBorders().apply(image, ctx) is image


def test_explicit_color_and_tolerance_handle_noisy_corners(ctx):
    image = framed()
    image.putpixel((0, 0), (254, 254, 254))
    result = TrimBorders(background="#ffffff", tolerance=10).apply(image, ctx)
    assert result.size == (60, 20)


def test_explicit_color_trims_a_border_on_one_side(ctx):
    image = framed(size=(100, 60), box=(20, 0, 100, 60))
    result = TrimBorders(background="white").apply(image, ctx)
    assert result.size == (80, 60)
    assert ctx.changes == {"trim": "L20 T0 R0 B0"}


@pytest.mark.parametrize("bg", [(0, 0, 0), (30, 90, 200), (250, 250, 250)])
def test_auto_finds_any_solid_border_color(ctx, bg):
    assert TrimBorders().apply(framed(bg=bg), ctx).size == (60, 20)


@pytest.mark.parametrize("name", ["#ff0000", "red", "#FF0000"])
def test_color_formats(ctx, name):
    image = framed(bg=(255, 0, 0), content=(0, 0, 255))
    assert TrimBorders(background=name).apply(image, ctx).size == (60, 20)


def test_explicit_background_that_does_not_match_cuts_nothing(ctx):
    image = framed()
    assert TrimBorders(background="black").apply(image, ctx) is image


# ---------- background: auto with a tolerance ----------

def with_corners(tl, tr, bl, br):
    image = framed()
    for xy, color in zip([(0, 0), (99, 0), (0, 59), (99, 59)], [tl, tr, bl, br]):
        image.putpixel(xy, color)
    return image


def test_tolerance_lets_slightly_different_corners_agree(ctx):
    image = with_corners((254, 254, 254), (255, 255, 255), (255, 255, 255), (253, 253, 253))
    assert TrimBorders().apply(image, ctx) is image  # default tolerance 0: exact
    assert TrimBorders(tolerance=0).apply(image, ctx) is image
    assert TrimBorders(tolerance=1).apply(image, ctx) is image  # 254 vs 253 is fine, but 255 vs 253 is 2
    assert TrimBorders(tolerance=2).apply(image, ctx).size == (60, 20)


def test_corner_agreement_is_checked_between_every_pair(ctx):
    # Each corner is within 2 of the top-left one, but TR and BL differ from each other by 4.
    image = framed(bg=(250, 250, 250))
    for xy, color in zip([(0, 0), (99, 0), (0, 59), (99, 59)], [250, 252, 248, 250]):
        image.putpixel(xy, (color,) * 3)
    assert TrimBorders(tolerance=2).apply(image, ctx) is image
    assert TrimBorders(tolerance=4).apply(image, ctx).size == (60, 20)


def test_a_difference_in_any_channel_counts_for_the_corners(ctx):
    image = with_corners((255, 255, 255), (255, 255, 250), (255, 255, 255), (255, 255, 255))
    assert TrimBorders(tolerance=4).apply(image, ctx) is image
    assert TrimBorders(tolerance=5).apply(image, ctx).size == (60, 20)


def test_noisy_margin_needs_a_tolerance_in_auto_mode(ctx):
    rng = random.Random(2)
    image = Image.new("RGB", (100, 60))
    pixels = image.load()
    for x in range(100):
        for y in range(60):
            n = rng.randint(-2, 2)
            pixels[x, y] = (252 + n, 252 + n, 250 + n)
    image.paste(RED, (12, 8, 72, 28))
    corners = {image.getpixel(xy) for xy in [(0, 0), (99, 0), (0, 59), (99, 59)]}
    assert len(corners) > 1  # the generated noise really makes the corners differ

    assert TrimBorders().apply(image, ctx) is image
    assert TrimBorders(tolerance=3).apply(image, ctx) is image  # corners may differ by 4 here
    result = TrimBorders(tolerance=4).apply(image, ctx)
    assert result.size == (60, 20)


def test_auto_uses_the_top_left_corner_as_the_color_with_a_tolerance(ctx):
    image = framed(bg=(253, 253, 253))
    image.putpixel((0, 0), (250, 250, 250))  # top-left is 3 darker than the rest of the margin
    assert TrimBorders(tolerance=2).apply(image, ctx) is image  # corners differ by 3
    # With 3 the corners agree and the margin (3 from the top-left color) is border.
    assert TrimBorders(tolerance=3).apply(image, ctx).size == (60, 20)


def test_transparent_corners_with_low_alpha_agree_with_a_tolerance(ctx):
    image = transparent_frame()
    for xy, alpha in zip([(0, 0), (99, 0), (0, 59), (99, 59)], [0, 2, 1, 3]):
        image.putpixel(xy, (7, 7, 7, alpha))
    assert TrimBorders().apply(image, ctx) is image  # exact: corners differ
    assert TrimBorders(tolerance=2).apply(image, ctx) is image  # one corner has alpha 3 > 2
    assert TrimBorders(tolerance=3).apply(image, ctx).size == (60, 20)


def test_opaque_and_transparent_corners_never_agree(ctx):
    image = transparent_frame()
    image.putpixel((99, 59), (200, 30, 30, 255))
    assert TrimBorders(tolerance=100).apply(image, ctx) is image


def test_tolerance_is_also_used_for_the_border_pixels_in_auto_mode(ctx):
    image = framed()
    image.putpixel((5, 5), (253, 253, 253))  # a speck, 2 off the margin color
    assert TrimBorders().apply(image, ctx).size == (67, 23)  # exact: the speck is content
    assert TrimBorders(tolerance=2).apply(image, ctx).size == (60, 20)


# ---------- tolerance ----------

def test_difference_equal_to_the_tolerance_is_still_border(ctx):
    image = framed(bg=(250, 250, 250))
    assert TrimBorders(background="white", tolerance=5).apply(image, ctx).size == (60, 20)


def test_difference_above_the_tolerance_is_content(ctx):
    image = framed(bg=(250, 250, 250))
    assert TrimBorders(background="white", tolerance=4).apply(image, ctx) is image


def test_zero_tolerance_is_exact(ctx):
    image = framed()
    image.putpixel((5, 5), (254, 255, 255))  # a speck in the margin
    assert TrimBorders(background="white", tolerance=0).apply(image, ctx).size == (67, 23)
    assert TrimBorders(background="white", tolerance=1).apply(image, ctx).size == (60, 20)


def test_the_largest_channel_difference_counts(ctx):
    image = framed()
    image.putpixel((5, 5), (255, 255, 240))  # only blue differs, by 15
    assert TrimBorders(background="white", tolerance=14).apply(image, ctx).size == (67, 23)
    assert TrimBorders(background="white", tolerance=15).apply(image, ctx).size == (60, 20)


# ---------- transparency ----------

def transparent_frame(box=(12, 8, 72, 28), size=(100, 60), alpha=255):
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.paste((200, 30, 30, alpha), box)
    return image


def test_auto_trims_a_transparent_border(ctx):
    result = TrimBorders().apply(transparent_frame(), ctx)
    assert result.size == (60, 20) and result.mode == "RGBA"
    assert ctx.changes == {"trim": "L12 T8 R28 B32"}


def test_hidden_rgb_of_transparent_corners_does_not_matter(ctx):
    image = transparent_frame()
    image.putpixel((0, 0), (255, 255, 255, 0))
    image.putpixel((99, 59), (10, 20, 30, 0))
    assert TrimBorders().apply(image, ctx).size == (60, 20)


def test_alpha_of_the_content_is_kept(ctx):
    result = TrimBorders().apply(transparent_frame(alpha=128), ctx)
    assert result.getpixel((0, 0)) == (200, 30, 30, 128)


def test_transparent_background_uses_alpha_and_tolerance(ctx):
    image = Image.new("RGBA", (100, 60), (9, 9, 9, 3))  # nearly invisible margin
    image.paste((200, 30, 30, 20), (12, 8, 72, 28))
    assert TrimBorders(background="transparent", tolerance=10).apply(image, ctx).size == (60, 20)
    assert TrimBorders(background="transparent", tolerance=2).apply(image, ctx) is image


def test_transparent_background_needs_no_corner_agreement(ctx):
    image = transparent_frame(box=(20, 0, 100, 60))  # transparent strip on the left only
    assert TrimBorders().apply(image, ctx) is image  # auto: corners disagree
    assert TrimBorders(background="transparent").apply(image, ctx).size == (80, 60)


def test_transparent_areas_count_as_the_given_color(ctx):
    result = TrimBorders(background="white").apply(transparent_frame(), ctx)
    assert result.size == (60, 20)


# ---------- modes ----------

def test_grayscale_image(ctx):
    image = Image.new("L", (100, 60), 255)
    image.paste(40, (12, 8, 72, 28))
    result = TrimBorders().apply(image, ctx)
    assert result.size == (60, 20) and result.mode == "L"


def test_grayscale_with_alpha(ctx):
    image = Image.new("LA", (100, 60), (0, 0))
    image.paste((100, 255), (12, 8, 72, 28))
    result = TrimBorders().apply(image, ctx)
    assert result.size == (60, 20) and result.mode == "LA"


def test_palette_image_is_converted_when_cut_and_untouched_when_not(ctx):
    cut = TrimBorders().apply(framed().convert("P"), ctx)
    assert cut.size == (60, 20) and cut.mode == "RGB"
    plain = Image.new("RGB", (10, 10), RED).convert("P")
    assert TrimBorders().apply(plain, ctx) is plain


def test_one_pixel_and_tiny_images(ctx):
    one = Image.new("RGB", (1, 1), WHITE)
    assert TrimBorders().apply(one, ctx) is one
    tiny = framed(size=(3, 3), box=(1, 1, 2, 2))
    assert TrimBorders().apply(tiny, ctx).size == (1, 1)


# ---------- validation ----------

@pytest.mark.parametrize(
    "options, message",
    [
        ({"tolerance": -1}, "'tolerance' must be between 0 and 255"),
        ({"tolerance": 256}, "'tolerance' must be between 0 and 255"),
        ({"tolerance": "5"}, "option 'tolerance' must be int"),
        ({"tolerance": True}, "option 'tolerance' must be int"),
        ({"tolerance": 2.5}, "option 'tolerance' must be int"),
        ({"background": 5}, "option 'background' must be str"),
        ({"background": "nope"}, "invalid background color 'nope'"),
        ({"background": "#12"}, "invalid background color"),
        ({"colour": "white"}, "unknown option"),
    ],
)
def test_invalid_options_rejected(options, message):
    with pytest.raises(ConfigError, match=f"step 'trim_borders'.*{message}"):
        create_step("trim_borders", options)


def test_defaults():
    step = create_step("trim_borders", {})
    assert (step.background, step.tolerance) == ("auto", 0)


# ---------- in the pipeline ----------

def save_framed(tmp_path, relpath, **kwargs):
    path = tmp_path / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    framed(**kwargs).save(path)
    return path


def run_with_reports(pipeline, tmp_path, seed=1, dry_run=False, out="out"):
    reports = []
    result = pipeline.run(tmp_path / "in", tmp_path / out, random.Random(seed), reports.append, dry_run=dry_run)
    return result, reports


def build(*specs):
    return Pipeline([create_step(name, options) for name, options in specs])


TRIM = ("trim_borders", {})
RESIZE = ("resize", {"size": 10})
SATURATE = ("rnd_saturation", {"min_percent": 20, "max_percent": 20})


def test_report_order_and_sizes(tmp_path):
    save_framed(tmp_path, "in/a.png")
    _, reports = run_with_reports(build(TRIM, RESIZE, SATURATE), tmp_path)
    assert list(reports[0].changes) == ["size", "trim", "saturation"]
    assert reports[0].changes["size"] == "100x60 -> 10x3"
    assert reports[0].changes["trim"] == "L12 T8 R28 B32"


def test_images_without_a_border_get_no_trim_entry(make_image, tmp_path):
    save_framed(tmp_path, "in/a.png")
    make_image("in/b.png", size=(100, 60), color=(150, 110, 90))
    _, reports = run_with_reports(build(TRIM), tmp_path)
    assert "trim" in reports[0].changes and "trim" not in reports[1].changes
    assert reports[1].changes == {"size": "100x60 (unchanged)"}


def test_written_file_is_trimmed(tmp_path):
    save_framed(tmp_path, "in/a.png")
    run_with_reports(build(TRIM), tmp_path)
    with Image.open(tmp_path / "out/a.png") as out:
        assert out.size == (60, 20)


@pytest.mark.parametrize(
    "specs",
    [
        [TRIM, RESIZE],
        [RESIZE, TRIM],
        [TRIM, RESIZE, SATURATE],
        [SATURATE, TRIM],
        [SATURATE, TRIM, ("resize", {"mode": "padding", "size": 30, "fill": "white"})],
    ],
)
def test_dry_run_reports_equal_real_run_reports(make_image, tmp_path, specs):
    save_framed(tmp_path, "in/a.png")
    save_framed(tmp_path, "in/sub/b.png", size=(80, 80), box=(5, 5, 60, 70), bg=(0, 0, 0))
    save_framed(tmp_path, "in/gray.png", mode="L", bg=255, content=40)
    make_image("in/plain.png", size=(100, 60), color=(150, 110, 90))
    pipeline = build(*specs)
    _, real = run_with_reports(pipeline, tmp_path, seed=4, out="real")
    _, dry = run_with_reports(pipeline, tmp_path, seed=4, dry_run=True, out="dry")
    assert real and dry == real
