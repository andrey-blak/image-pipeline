import random

import pytest
from PIL import Image, ImageOps

from imgpipe.errors import PresetError
from imgpipe.pipeline import Pipeline
from imgpipe.steps import Context, create_step
from imgpipe.steps.auto_brightness import AutoBrightness, _levels


def random_image(mode, lo, hi, seed=1, size=(40, 30)):
    rng = random.Random(seed)
    bands = len(mode)
    image = Image.new(mode, size)
    values = (
        [rng.randint(lo, hi) for _ in range(size[0] * size[1])]
        if bands == 1
        else [tuple(rng.randint(lo, hi) for _ in range(bands)) for _ in range(size[0] * size[1])]
    )
    image.putdata(values)
    return image


def gray(value, size=(10, 10)):
    return Image.new("L", size, value)


# ---------- autocontrast ----------

@pytest.mark.parametrize("mode", ["L", "RGB"])
@pytest.mark.parametrize("cutoff", [0, 0.1, 0.5, 2, 10, 25])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_levels_stretch_equals_pillows_preserve_tone_autocontrast(ctx, mode, cutoff, seed):
    image = random_image(mode, 60 + seed * 5, 190 - seed * 7, seed=seed)
    result = AutoBrightness(cutoff=cutoff).apply(image, ctx)
    expected = ImageOps.autocontrast(image, cutoff=cutoff, preserve_tone=True)
    assert result.tobytes() == expected.tobytes()


def test_reports_the_levels_that_were_found(ctx):
    image = gray(60, (20, 10))
    image.paste(120, (10, 0, 20, 10))
    result = AutoBrightness(cutoff=0).apply(image, ctx)
    assert ctx.changes == {"brightness": "levels 60-120 -> 0-255"}
    assert result.getextrema() == (0, 255)


def test_default_cutoff_is_half_a_percent(ctx):
    assert AutoBrightness().cutoff == 0.5


def test_cutoff_ignores_a_hot_pixel(ctx):
    image = gray(100, (40, 30))
    image.paste(150, (20, 0, 40, 30))
    image.putpixel((0, 0), 255)  # 1 of 1200 pixels
    AutoBrightness(cutoff=0).apply(image, ctx)
    assert ctx.changes == {"brightness": "levels 100-255 -> 0-255"}
    ctx.changes.clear()
    AutoBrightness(cutoff=1).apply(image, ctx)
    assert ctx.changes == {"brightness": "levels 100-150 -> 0-255"}


def test_image_using_the_full_range_is_left_alone(ctx):
    image = gray(100, (40, 30))
    image.putpixel((0, 0), 0)
    image.putpixel((1, 0), 255)
    assert AutoBrightness(cutoff=0).apply(image, ctx) is image
    assert ctx.changes == {}


def test_flat_image_is_left_alone(ctx):
    image = Image.new("RGB", (8, 8), (90, 120, 150))
    assert AutoBrightness().apply(image, ctx) is image
    assert ctx.changes == {}


def test_colors_keep_their_balance(ctx):
    image = Image.new("RGB", (30, 10), (90, 90, 90))
    image.paste((170, 170, 170), (10, 0, 20, 10))
    image.paste((170, 140, 100), (20, 0, 30, 10))  # a warm tint
    result = AutoBrightness(cutoff=0).apply(image, ctx)
    dark, light, warm = (result.getpixel(xy) for xy in [(0, 0), (15, 5), (25, 5)])
    assert dark[0] == dark[1] == dark[2] and light[0] == light[1] == light[2]
    assert warm[0] > warm[1] > warm[2]


def test_the_same_adjustment_is_used_for_every_channel(ctx):
    image = Image.new("RGB", (4, 1))
    image.putdata([(60, 60, 60), (120, 120, 120), (60, 120, 90), (120, 60, 90)])
    result = AutoBrightness(cutoff=0).apply(image, ctx)
    assert result.getpixel((2, 0))[:2] == (result.getpixel((0, 0))[0], result.getpixel((1, 0))[0])
    assert result.getpixel((3, 0))[:2] == (result.getpixel((1, 0))[0], result.getpixel((0, 0))[0])


def test_levels_helper_matches_a_hand_computed_case():
    histogram = [0] * 256
    histogram[10], histogram[20], histogram[200] = 50, 940, 10  # 1000 pixels
    assert _levels(histogram, 0) == (10, 200)
    assert _levels(histogram, 1) == (10, 20)  # 1% = 10 pixels: removes the 200s
    assert _levels(histogram, 6) == (20, 20)  # 6% = 60 pixels: the 10s, and 10 of the 20s
    assert _levels([0] * 256, 0) == (255, 0)


# ---------- target_mean ----------

def target(**options):
    return AutoBrightness(method="target_mean", **options)


def test_dark_image_is_brightened_up_to_the_limit(ctx):
    result = target().apply(gray(60), ctx)
    assert ctx.changes == {"brightness": "x1.30 (mean 60, target 128, limited)"}
    assert result.getpixel((0, 0)) == 78


def test_factor_within_the_limits_is_not_marked_limited(ctx):
    result = target().apply(gray(110), ctx)
    assert ctx.changes == {"brightness": "x1.16 (mean 110, target 128)"}
    assert abs(result.getpixel((0, 0)) - 110 * 128 / 110) <= 1


def test_bright_image_is_darkened(ctx):
    result = target().apply(gray(200), ctx)
    assert ctx.changes == {"brightness": "x0.70 (mean 200, target 128, limited)"}
    assert result.getpixel((0, 0)) == 140


def test_max_change_widens_the_limit(ctx):
    target(max_change=0.5).apply(gray(200), ctx)
    assert ctx.changes == {"brightness": "x0.64 (mean 200, target 128)"}


def test_custom_target(ctx):
    target(target=150, max_change=0.5).apply(gray(100), ctx)
    assert ctx.changes == {"brightness": "x1.50 (mean 100, target 150)"}


def test_image_at_the_target_is_left_alone(ctx):
    image = gray(128)
    assert target().apply(image, ctx) is image
    assert ctx.changes == {}


def test_black_image_is_left_alone(ctx):
    image = gray(0)
    assert target().apply(image, ctx) is image
    assert ctx.changes == {}


def test_rgb_values_are_scaled_and_clipped(ctx):
    image = Image.new("RGB", (4, 4), (100, 200, 250))  # luminance mean 176
    result = target().apply(image, ctx)
    assert ctx.changes["brightness"] == "x0.73 (mean 176, target 128)"
    assert all(abs(a - b * 128 / 176) <= 1 for a, b in zip(result.getpixel((0, 0)), (100, 200, 250)))
    ctx.changes.clear()
    bright = target(target=200).apply(Image.new("RGB", (4, 4), (250, 100, 40)), ctx)
    assert bright.getpixel((0, 0))[0] == 255  # clipped


# ---------- both methods: modes and transparency ----------

METHOD_OPTIONS = [{}, {"method": "target_mean"}]


def opaque_dark_with_hidden_white(alpha_hidden=0):
    """Dark gray content in the top rows, a white-RGB area with the given alpha below."""
    image = Image.new("RGBA", (40, 30), (100, 100, 100, 255))
    image.paste((150, 150, 150, 255), (20, 0, 40, 20))
    image.paste((255, 255, 255, alpha_hidden), (0, 20, 40, 30))
    return image


def test_autocontrast_ignores_transparent_pixels(ctx):
    result = AutoBrightness(cutoff=0).apply(opaque_dark_with_hidden_white(), ctx)
    assert ctx.changes == {"brightness": "levels 100-150 -> 0-255"}
    assert result.mode == "RGBA"
    assert result.getpixel((0, 25))[3] == 0 and result.getpixel((0, 0))[3] == 255


def test_target_mean_ignores_transparent_pixels(ctx):
    image = Image.new("RGBA", (40, 30), (100, 100, 100, 255))
    image.paste((255, 255, 255, 0), (0, 20, 40, 30))
    target().apply(image, ctx)
    assert ctx.changes == {"brightness": "x1.28 (mean 100, target 128)"}


@pytest.mark.parametrize("options", METHOD_OPTIONS)
def test_semi_transparent_pixels_count_and_alpha_is_kept(ctx, options):
    image = Image.new("RGBA", (20, 10), (80, 80, 80, 128))
    image.paste((120, 120, 120, 40), (10, 0, 20, 10))
    result = AutoBrightness(**options).apply(image, ctx)
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 128 and result.getpixel((15, 5))[3] == 40
    assert ctx.changes


@pytest.mark.parametrize("options", METHOD_OPTIONS)
def test_fully_transparent_image_is_left_alone(ctx, options):
    image = Image.new("RGBA", (8, 8), (200, 200, 200, 0))
    assert AutoBrightness(**options).apply(image, ctx) is image
    assert ctx.changes == {}


@pytest.mark.parametrize("options", METHOD_OPTIONS)
def test_grayscale_and_grayscale_with_alpha(ctx, options):
    dark = random_image("L", 40, 90)
    assert AutoBrightness(**options).apply(dark, ctx).mode == "L"
    la = Image.new("LA", (20, 10), (60, 200))
    la.paste((90, 77), (10, 0, 20, 10))
    result = AutoBrightness(**options).apply(la, ctx)
    assert result.mode == "LA" and result.getpixel((15, 5))[1] == 77


@pytest.mark.parametrize("options", METHOD_OPTIONS)
def test_palette_image_is_converted(ctx, options):
    palette = random_image("RGB", 40, 100).convert("P")
    result = AutoBrightness(**options).apply(palette, ctx)
    assert result.mode == "RGB"


@pytest.mark.parametrize("options", METHOD_OPTIONS)
def test_input_image_is_not_modified(ctx, options):
    image = random_image("RGB", 40, 100)
    before = image.tobytes()
    AutoBrightness(**options).apply(image, ctx)
    assert image.tobytes() == before


# ---------- validation ----------

@pytest.mark.parametrize(
    "options, message",
    [
        ({"method": "spin"}, "unknown method 'spin'; known methods: autocontrast, target_mean"),
        ({"method": "target_mean", "cutoff": 1}, "option 'cutoff' is not used by method 'target_mean'"),
        ({"target": 100}, "option 'target' is not used by method 'autocontrast'"),
        ({"max_change": 0.2}, "option 'max_change' is not used by method 'autocontrast'"),
        ({"cutoff": -1}, "'cutoff' must be at least 0 and below 50"),
        ({"cutoff": 50}, "'cutoff' must be at least 0 and below 50"),
        ({"method": "target_mean", "target": -1}, "'target' must be between 0 and 255"),
        ({"method": "target_mean", "target": 256}, "'target' must be between 0 and 255"),
        ({"method": "target_mean", "max_change": 0}, "'max_change' must be above 0 and at most 1"),
        ({"method": "target_mean", "max_change": -0.1}, "'max_change' must be above 0 and at most 1"),
        ({"method": "target_mean", "max_change": 1.5}, "'max_change' must be above 0 and at most 1"),
        ({"cutoff": "5"}, "option 'cutoff' must be float"),
        ({"cutoff": True}, "option 'cutoff' must be float"),
        ({"method": "target_mean", "target": 1.5}, "option 'target' must be int"),
        ({"method": 3}, "option 'method' must be str"),
    ],
)
def test_invalid_options_rejected(options, message):
    with pytest.raises(PresetError, match=f"step 'auto_brightness'.*{message}"):
        create_step("auto_brightness", options)


def test_defaults_are_filled_in_for_the_chosen_method():
    step = create_step("auto_brightness", {})
    assert (step.method, step.cutoff, step.target, step.max_change) == ("autocontrast", 0.5, None, None)
    step = create_step("auto_brightness", {"method": "target_mean"})
    assert (step.cutoff, step.target, step.max_change) == (None, 128, 0.3)


def test_int_cutoff_is_accepted():
    assert create_step("auto_brightness", {"cutoff": 2}).cutoff == 2


# ---------- in the pipeline ----------

def build(*specs):
    return Pipeline([create_step(name, options) for name, options in specs])


def run_with_reports(pipeline, tmp_path, seed=1, dry_run=False, out="out"):
    reports = []
    result = pipeline.run(tmp_path / "in", tmp_path / out, random.Random(seed), reports.append, dry_run=dry_run)
    return result, reports


def save(tmp_path, relpath, image):
    path = tmp_path / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


RESIZE = ("resize", {"size": 20})
BRIGHT = ("auto_brightness", {"cutoff": 0})
TARGET = ("auto_brightness", {"method": "target_mean"})
SATURATE = ("rnd_saturation", {"min_percent": 3, "max_percent": 40})


def test_report_order_for_a_full_pipeline(tmp_path):
    framed = Image.new("RGB", (100, 60), (255, 255, 255))
    framed.paste(random_image("RGB", 60, 140, size=(60, 20)), (12, 8))
    save(tmp_path, "in/a.png", framed)
    _, reports = run_with_reports(
        build(("trim_borders", {}), RESIZE, BRIGHT, SATURATE), tmp_path
    )
    assert list(reports[0].changes) == ["size", "trim", "brightness", "saturation"]
    assert reports[0].changes["brightness"].startswith("levels ")


def test_no_entry_when_nothing_changed_and_no_leakage(tmp_path):
    save(tmp_path, "in/a.png", random_image("RGB", 60, 140))
    full = gray(100, (40, 30))  # already uses black and white
    full.putpixel((0, 0), 0)
    full.putpixel((1, 0), 255)
    save(tmp_path, "in/b.png", full)
    _, reports = run_with_reports(build(BRIGHT), tmp_path)
    assert "brightness" in reports[0].changes and "brightness" not in reports[1].changes


@pytest.mark.parametrize(
    "specs",
    [
        [RESIZE, BRIGHT],
        [BRIGHT, RESIZE],
        [RESIZE, BRIGHT, SATURATE],
        [SATURATE, BRIGHT],
        [RESIZE, TARGET, SATURATE],
        [SATURATE, TARGET, RESIZE],
        [("resize", {"mode": "padding", "size": 30, "fill": "white"}), BRIGHT],
    ],
)
def test_dry_run_reports_equal_real_run_reports(tmp_path, specs):
    save(tmp_path, "in/dark.png", random_image("RGB", 40, 120, size=(80, 50)))
    save(tmp_path, "in/sub/bright.png", random_image("RGB", 150, 250, seed=2, size=(50, 80)))
    save(tmp_path, "in/gray.png", random_image("L", 60, 140, seed=3))
    save(tmp_path, "in/alpha.png", opaque_dark_with_hidden_white())
    save(tmp_path, "in/full.png", random_image("RGB", 0, 255, seed=4))
    pipeline = build(*specs)
    _, real = run_with_reports(pipeline, tmp_path, seed=6, out="real")
    _, dry = run_with_reports(pipeline, tmp_path, seed=6, dry_run=True, out="dry")
    assert real and dry == real
