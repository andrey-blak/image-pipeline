import random
from pathlib import Path

import pytest
from PIL import Image

from imgpipe.pipeline import Pipeline
from imgpipe.steps import Context, Step, create_step
from imgpipe.steps.resize import Resize
from imgpipe.steps.rnd_saturation import RandomSaturation


# ---------- step declarations ----------

def test_undeclared_step_depends_on_everything():
    assert Step.depends_on_pixels is True and Step.depends_on_size is True


def test_auto_brightness_reads_pixels_but_not_the_size():
    from imgpipe.steps.auto_brightness import AutoBrightness

    assert (AutoBrightness.depends_on_pixels, AutoBrightness.depends_on_size) == (True, False)


def test_declared_dependencies():
    assert (Resize.depends_on_pixels, Resize.depends_on_size) == (False, True)
    # Saturation reads the image mode (grayscale or not), which counts as pixels.
    assert (RandomSaturation.depends_on_pixels, RandomSaturation.depends_on_size) == (True, False)


# ---------- flag computation ----------

def spy(pixels=False, size=False):
    class Spy(Step):
        depends_on_pixels = pixels
        depends_on_size = size

        def __init__(self):
            self.seen = []

        def apply(self, image, ctx):
            self.seen.append((ctx.skip_pixels, ctx.skip_resize))
            return image

    return Spy()


def run_process(steps, dry_run, ctx=None):
    ctx = ctx or Context(rng=random.Random(1))
    Pipeline(steps).process(Image.new("RGB", (4, 4)), ctx, dry_run)
    return ctx


def test_real_run_never_skips():
    a, b = spy(), spy()
    ctx = run_process([a, b], dry_run=False)
    assert a.seen == [(False, False)] and b.seen == [(False, False)]
    assert (ctx.skip_pixels, ctx.skip_resize) == (False, False)


def test_last_step_may_skip_everything():
    a, b = spy(pixels=True, size=True), spy(pixels=True, size=True)
    run_process([a, b], dry_run=True)
    assert b.seen == [(True, True)]


def test_step_before_pixel_dependent_step_keeps_pixels_but_may_skip_size():
    a, b = spy(), spy(pixels=True)
    run_process([a, b], dry_run=True)
    assert a.seen == [(False, True)]


def test_step_before_size_dependent_step_keeps_size_but_may_skip_pixels():
    a, b = spy(), spy(size=True)
    run_process([a, b], dry_run=True)
    assert a.seen == [(True, False)]


def test_any_later_dependent_step_counts_not_only_the_next():
    a, b, c = spy(), spy(), spy(pixels=True, size=True)
    run_process([a, b, c], dry_run=True)
    assert a.seen == [(False, False)] and b.seen == [(False, False)]


def test_undeclared_later_step_blocks_skipping():
    a, b = spy(), Step.__new__(Step)  # Step defaults: depends on everything
    b.apply = lambda image, ctx: image
    run_process([a, b], dry_run=True)
    assert a.seen == [(False, False)]


def test_flags_are_reset_after_processing():
    ctx = run_process([spy()], dry_run=True)
    assert (ctx.skip_pixels, ctx.skip_resize) == (False, False)


# ---------- resize ----------

RESIZE_CASES = [
    {"size": 300},
    {"size": 300, "upscale": True},
    {"mode": "padding", "width": 300, "height": 200},
    {"mode": "padding", "size": 300, "upscale": True, "fill": "white"},
    {"mode": "crop", "width": 300, "height": 200},
    {"mode": "crop", "size": 300, "upscale": True},
]
IMAGE_SIZES = [(600, 400), (400, 600), (300, 300), (100, 50), (50, 100), (300, 200), (5000, 3), (3, 5000)]


@pytest.mark.parametrize("options", RESIZE_CASES)
@pytest.mark.parametrize("size", IMAGE_SIZES)
def test_output_size_matches_the_real_result(ctx, options, size):
    step = create_step("resize", options)
    real = step.apply(Image.new("RGB", size), ctx)
    assert step._output_size(size) == real.size


def test_resize_skipping_pixels_only_gives_blank_image_of_the_right_size(ctx):
    step = Resize(size=10)
    ctx.skip_pixels = True
    result = step.apply(Image.new("RGB", (40, 20), (200, 100, 50)), ctx)
    assert result.size == (10, 5)
    assert result.getpixel((0, 0)) == (0, 0, 0)  # blank, not resampled
    assert ctx.reported_size is None


def test_resize_skipping_everything_returns_same_image_and_reports_size(ctx):
    step = Resize(size=10)
    image = Image.new("RGB", (40, 20))
    ctx.skip_pixels = ctx.skip_resize = True
    assert step.apply(image, ctx) is image
    assert ctx.reported_size == (10, 5)


def test_resize_same_size_input_returned_unchanged_in_every_mode(ctx):
    image = Image.new("RGB", (10, 10))
    for flags in [(False, False), (True, False), (True, True)]:
        ctx.skip_pixels, ctx.skip_resize = flags
        assert Resize(size=10).apply(image, ctx) is image
        assert ctx.reported_size is None


def test_resize_ignores_skip_resize_when_pixels_are_needed(ctx):
    ctx.skip_pixels, ctx.skip_resize = False, True
    assert Resize(size=10).apply(Image.new("RGB", (40, 20)), ctx).size == (10, 5)


# ---------- saturation ----------

def test_saturation_skipping_pixels_keeps_image_but_records_and_draws_the_same():
    step = RandomSaturation(min_percent=3, max_percent=40)
    image = Image.new("RGB", (4, 4), (150, 110, 90))
    real_ctx, dry_ctx = Context(rng=random.Random(7)), Context(rng=random.Random(7))
    dry_ctx.skip_pixels = True

    real = step.apply(image, real_ctx)
    dry = step.apply(image, dry_ctx)

    assert dry is image and real.tobytes() != image.tobytes()
    assert dry_ctx.changes == real_ctx.changes
    assert dry_ctx.rng.random() == real_ctx.rng.random()


@pytest.mark.parametrize("skip", [False, True])
def test_saturation_grayscale_recorded_in_both_modes(ctx, skip):
    ctx.skip_pixels = skip
    RandomSaturation(min_percent=5, max_percent=5).apply(Image.new("L", (4, 4), 100), ctx)
    assert ctx.changes == {"saturation": "n/a (grayscale)"}


# ---------- pipeline dry run ----------

CONFIGS = {
    "resize+saturation": [("resize", {"size": 100}), ("rnd_saturation", {"min_percent": 3, "max_percent": 40})],
    "padding+saturation": [
        ("resize", {"mode": "padding", "width": 100, "height": 60, "fill": "white"}),
        ("rnd_saturation", {"min_percent": 3, "max_percent": 40}),
    ],
    "crop": [("resize", {"mode": "crop", "width": 100, "height": 60})],
    "saturation+resize": [("rnd_saturation", {"min_percent": 3, "max_percent": 40}), ("resize", {"size": 100})],
    "resize+resize": [("resize", {"size": 100}), ("resize", {"mode": "padding", "size": 80})],
    "saturation only": [("rnd_saturation", {"min_percent": 3, "max_percent": 40})],
}


def build(specs):
    return Pipeline([create_step(name, options) for name, options in specs])


def reports_of(pipeline, src, dst, seed, dry_run):
    reports = []
    result = pipeline.run(src, dst, random.Random(seed), reports.append, dry_run=dry_run)
    return result, reports


@pytest.fixture
def tree(make_image, tmp_path):
    make_image("in/a.png", size=(600, 400), color=(150, 110, 90))
    make_image("in/b.jpg", size=(400, 600), color=(150, 110, 90))
    make_image("in/sub/c.png", size=(50, 30), color=(150, 110, 90))
    make_image("in/sub/deep/d.png", size=(300, 300), color=(150, 110, 90))
    make_image("in/gray.png", size=(80, 60), mode="L", color=100)
    return tmp_path


@pytest.mark.parametrize("name", CONFIGS)
def test_dry_run_reports_equal_real_run_reports(tree, name):
    pipeline = build(CONFIGS[name])
    _, real = reports_of(pipeline, tree / "in", tree / "real", seed=3, dry_run=False)
    _, dry = reports_of(pipeline, tree / "in", tree / "dry", seed=3, dry_run=True)
    assert real and dry == real


def test_dry_run_writes_nothing(tree):
    before = sorted(p for p in tree.rglob("*"))
    result, _ = reports_of(build(CONFIGS["resize+saturation"]), tree / "in", tree / "out", 1, dry_run=True)

    assert not (tree / "out").exists()
    assert sorted(tree.rglob("*")) == before
    assert len(result.processed) == 5 and not result.skipped


def test_dry_run_lists_would_be_targets(tree):
    result, _ = reports_of(build(CONFIGS["crop"]), tree / "in", tree / "out", 1, dry_run=True)
    assert [p.relative_to((tree / "out").resolve()).as_posix() for p in result.processed] == [
        "a.png", "b.jpg", "gray.png", "sub/c.png", "sub/deep/d.png",
    ]


def test_dry_run_leaves_originals_untouched(tree):
    originals = {p: p.read_bytes() for p in (tree / "in").rglob("*.png")}
    reports_of(build(CONFIGS["resize+saturation"]), tree / "in", tree / "out", 1, dry_run=True)
    assert {p: p.read_bytes() for p in originals} == originals


def test_dry_run_still_finds_unreadable_files(tree):
    (tree / "in/broken.png").write_bytes(b"junk")
    result, reports = reports_of(build(CONFIGS["crop"]), tree / "in", tree / "out", 1, dry_run=True)
    assert [Path(p).name for p, _ in result.skipped] == ["broken.png"]
    assert "broken.png" not in [r.source.name for r in reports]


def test_resize_before_saturation_runs_for_real_so_a_mode_change_is_seen(ctx):
    # padding turns a grayscale image into RGB; the later saturation must see that.
    resize = create_step("resize", {"mode": "padding", "size": 20, "fill": "white"})
    saturation = create_step("rnd_saturation", {"min_percent": 5, "max_percent": 5})
    ctx = Context(rng=random.Random(1))
    Pipeline([resize, saturation]).process(Image.new("L", (10, 5), 100), ctx, dry_run=True)
    assert ctx.changes == {"saturation": "+5.0%"}
