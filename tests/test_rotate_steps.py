import random
import re

import pytest
from PIL import Image

from imgpipe.errors import PresetError
from imgpipe.pipeline import Pipeline
from imgpipe.steps import Context, create_step, REGISTRY
from imgpipe.steps.rnd_rotate import RandomRotate
from imgpipe.steps.rotate import Rotate

RED = (200, 30, 30)


def photo(size=(60, 40), mode="RGB", seed=1):
    rng = random.Random(seed)
    image = Image.new(mode, size)
    bands = len(mode)
    image.putdata([
        tuple(rng.randint(0, 255) for _ in range(bands)) if bands > 1 else rng.randint(0, 255)
        for _ in range(size[0] * size[1])
    ])
    return image


def angle_of(ctx):
    return float(re.fullmatch(r"([+-]\d+(?:\.\d+)?)°", ctx.changes["rotation"]).group(1))


# ---------- rotate ----------

def test_registered():
    assert {"rotate", "rnd_rotate"} <= set(REGISTRY)


@pytest.mark.parametrize("angle, text", [(90, "+90°"), (-12.5, "-12.5°"), (12, "+12°"), (7.25, "+7.25°"),
                                         (-90, "-90°"), (180, "+180°")])
def test_rotation_is_recorded(ctx, angle, text):
    Rotate(angle=angle).apply(photo(), ctx)
    assert ctx.changes == {"rotation": text}


@pytest.mark.parametrize("angle", [0, 360, -360, 720])
def test_full_turns_do_nothing(ctx, angle):
    image = photo()
    assert Rotate(angle=angle).apply(image, ctx) is image
    assert ctx.changes == {}


def test_quarter_turn_swaps_the_sides_and_ignores_corners(ctx):
    result = Rotate(angle=90, corners="fill", fill="white").apply(photo((60, 40)), ctx)
    assert result.size == (40, 60) and result.mode == "RGB"


def test_default_is_crop(ctx):
    step = Rotate(angle=10)
    assert (step.corners, step.fill) == ("crop", None)
    result = step.apply(Image.new("RGB", (100, 60), RED), ctx)
    assert result.size == (76, 45) and result.getextrema() == ((200, 200), (30, 30), (30, 30))


def test_fill_with_a_color(ctx):
    result = Rotate(angle=10, corners="fill", fill="white").apply(Image.new("RGB", (100, 60), RED), ctx)
    assert result.size == (110, 78) and result.getpixel((0, 0)) == (255, 255, 255)


def test_fill_defaults_to_transparent(ctx):
    result = Rotate(angle=10, corners="fill").apply(Image.new("RGB", (100, 60), RED), ctx)
    assert result.mode == "RGBA" and result.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "LA"])
def test_modes_in_crop_mode_are_kept(ctx, mode):
    assert Rotate(angle=7).apply(photo(mode=mode), ctx).mode == mode


def test_palette_images_are_converted(ctx):
    assert Rotate(angle=7).apply(photo().convert("P"), ctx).mode == "RGB"


def test_input_is_not_modified(ctx):
    image = photo()
    before = image.tobytes()
    Rotate(angle=12).apply(image, ctx)
    assert image.tobytes() == before


@pytest.mark.parametrize(
    "options, message",
    [
        ({}, "missing required option 'angle'"),
        ({"angle": float("nan")}, "'angle' must be a finite number"),
        ({"angle": float("inf")}, "'angle' must be a finite number"),
        ({"angle": "5"}, "option 'angle' must be float"),
        ({"angle": True}, "option 'angle' must be float"),
        ({"angle": 5, "corners": "zoom"}, "unknown corners 'zoom'; known values: crop, fill"),
        ({"angle": 5, "fill": "white"}, "option 'fill' is not used by corners 'crop'"),
        ({"angle": 5, "corners": "fill", "fill": "nope"}, "invalid fill color 'nope'"),
        ({"angle": 5, "corners": 1}, "option 'corners' must be str"),
        ({"angle": 5, "fill": 1}, "option 'fill' must be str"),
        ({"angle": 5, "tilt": 1}, "unknown option"),
    ],
)
def test_rotate_validation(options, message):
    with pytest.raises(PresetError, match=f"step 'rotate'.*{message}"):
        create_step("rotate", options)


def test_integers_are_fine_for_the_angle():
    assert create_step("rotate", {"angle": 15}).angle == 15


# ---------- rnd_rotate ----------

def draws(step, count, seed=1, image=None):
    ctx = Context(rng=random.Random(seed))
    image = image or Image.new("RGB", (8, 8), RED)
    angles = []
    for _ in range(count):
        ctx.changes.clear()
        step.apply(image, ctx)
        angles.append(angle_of(ctx) if ctx.changes else 0.0)
    return angles


def test_defaults():
    step = RandomRotate()
    assert (step.min_angle, step.max_angle, step.corners, step.fill) == (0, 5, "crop", None)


def test_angles_stay_in_the_range_and_differ():
    angles = draws(RandomRotate(), 1000)
    assert all(abs(a) <= 5 for a in angles)
    assert len(set(angles)) > 100


def test_both_directions_occur_about_equally():
    positive = sum(a > 0 for a in draws(RandomRotate(), 1000))
    assert 400 <= positive <= 600


def test_min_and_max_are_absolute_values():
    angles = draws(RandomRotate(min_angle=2, max_angle=5), 1000)
    assert all(1.95 <= abs(a) <= 5.05 for a in angles)  # one decimal in the report
    assert any(a > 0 for a in angles) and any(a < 0 for a in angles)
    assert not any(-1.95 < a < 1.95 for a in angles)


def test_equal_min_and_max_give_exactly_that_angle_either_way():
    angles = draws(RandomRotate(min_angle=3, max_angle=3), 100)
    assert set(angles) == {3.0, -3.0}


def test_zero_range_rotates_nothing(ctx):
    image = photo()
    assert RandomRotate(min_angle=0, max_angle=0).apply(image, ctx) is image
    assert ctx.changes == {}


def test_same_seed_same_angles():
    assert draws(RandomRotate(), 50, seed=7) == draws(RandomRotate(), 50, seed=7)
    assert draws(RandomRotate(), 50, seed=7) != draws(RandomRotate(), 50, seed=8)


def test_angle_is_recorded_with_one_decimal(ctx):
    RandomRotate().apply(photo(), ctx)
    assert re.fullmatch(r"[+-]\d\.\d°", ctx.changes["rotation"])


def test_random_numbers_are_drawn_even_when_nothing_is_rotated():
    a, b = Context(rng=random.Random(5)), Context(rng=random.Random(5))
    RandomRotate(min_angle=0, max_angle=0).apply(photo(), a)
    RandomRotate(min_angle=1, max_angle=2).apply(photo(), b)
    assert a.rng.random() == b.rng.random()


def test_corner_options_work_as_in_rotate(ctx):
    result = RandomRotate(min_angle=3, max_angle=3, corners="fill", fill="white").apply(photo(), ctx)
    assert result.width > 60 and result.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize(
    "options, message",
    [
        ({"min_angle": -1}, "angles must satisfy 0 <= min_angle <= max_angle <= 180"),
        ({"max_angle": -1}, "angles must satisfy"),
        ({"min_angle": 6, "max_angle": 5}, "angles must satisfy"),
        ({"max_angle": 181}, "angles must satisfy"),
        ({"min_angle": "1"}, "option 'min_angle' must be float"),
        ({"max_angle": True}, "option 'max_angle' must be float"),
        ({"corners": "zoom"}, "unknown corners 'zoom'"),
        ({"fill": "white"}, "option 'fill' is not used by corners 'crop'"),
        ({"corners": "fill", "fill": "nope"}, "invalid fill color 'nope'"),
    ],
)
def test_rnd_rotate_validation(options, message):
    with pytest.raises(PresetError, match=f"step 'rnd_rotate'.*{message}"):
        create_step("rnd_rotate", options)


# ---------- in the pipeline ----------

def build(*specs):
    return Pipeline([create_step(name, options) for name, options in specs])


def save(tmp_path, relpath, image):
    path = tmp_path / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def run(pipeline, tmp_path, seed=3, dry_run=False, out="out"):
    reports = []
    result = pipeline.run(tmp_path / "in", tmp_path / out, random.Random(seed), reports.append, dry_run=dry_run)
    return result, reports


ROTATE = ("rnd_rotate", {"max_angle": 8})
FILL = ("rnd_rotate", {"max_angle": 8, "corners": "fill"})
RESIZE = ("resize", {"size": 30})
SATURATE = ("rnd_saturation", {"min_percent": 3, "max_percent": 40})
BRIGHT = ("auto_brightness", {})


def test_report_order_in_a_full_pipeline(tmp_path):
    framed = Image.new("RGB", (120, 80), (255, 255, 255))
    framed.paste(photo((80, 50), seed=4), (20, 10))
    save(tmp_path, "in/a.png", framed)
    _, reports = run(build(("trim_borders", {}), ROTATE, RESIZE, BRIGHT, SATURATE), tmp_path)
    assert list(reports[0].changes) == ["size", "trim", "rotation", "brightness", "saturation"]


def test_written_file_is_rotated_and_cropped(tmp_path):
    save(tmp_path, "in/a.png", Image.new("RGB", (100, 60), RED))
    run(build(("rotate", {"angle": 10})), tmp_path)
    with Image.open(tmp_path / "out/a.png") as out:
        assert out.size == (76, 45)


@pytest.mark.parametrize(
    "specs",
    [
        [ROTATE, RESIZE],
        [RESIZE, ROTATE],
        [FILL, RESIZE, SATURATE],
        [("rnd_rotate", {"max_angle": 8, "corners": "fill", "fill": "white"}), RESIZE, BRIGHT],
        [("rotate", {"angle": 90}), RESIZE],
        [("rotate", {"angle": 12.5, "corners": "fill"}), SATURATE],
        [ROTATE, SATURATE],
        [SATURATE, ROTATE, RESIZE],
    ],
)
def test_dry_run_reports_equal_real_run_reports(tmp_path, specs):
    save(tmp_path, "in/rgb.png", photo((80, 50), seed=1))
    save(tmp_path, "in/sub/tall.jpg", photo((50, 80), seed=2))
    save(tmp_path, "in/gray.png", photo((60, 60), "L", seed=3))
    save(tmp_path, "in/alpha.png", photo((70, 40), "RGBA", seed=4))
    pipeline = build(*specs)
    _, real = run(pipeline, tmp_path, seed=6, out="real")
    _, dry = run(pipeline, tmp_path, seed=6, dry_run=True, out="dry")
    assert real and dry == real
    assert not (tmp_path / "dry").exists()


def test_same_seed_repeats_the_whole_run(tmp_path):
    save(tmp_path, "in/a.png", photo((80, 50), seed=1))
    save(tmp_path, "in/b.png", photo((80, 50), seed=2))
    pipeline = build(ROTATE, RESIZE, SATURATE)
    _, first = run(pipeline, tmp_path, seed=11, out="o1")
    _, second = run(pipeline, tmp_path, seed=11, out="o2")
    _, other = run(pipeline, tmp_path, seed=12, out="o3")
    assert first == second and first != other
    assert (tmp_path / "o1/a.png").read_bytes() == (tmp_path / "o2/a.png").read_bytes()
