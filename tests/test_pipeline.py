import random

import pytest
from PIL import Image

from imgpipe import imageio, output
from imgpipe.errors import ConfigError
from imgpipe.pipeline import Pipeline
from imgpipe.steps import Context, create_step


def pipeline(*specs):
    return Pipeline([create_step(name, options) for name, options in specs])


RESIZE = ("resize", {"size": 10})
SATURATE = ("rnd_saturation", {"min_percent": 20, "max_percent": 20})


def test_steps_run_in_order(ctx):
    calls = []

    class Spy:
        def __init__(self, label):
            self.label = label

        def apply(self, image, ctx):
            calls.append(self.label)
            return image

    Pipeline([Spy("a"), Spy("b"), Spy("c")]).process(Image.new("RGB", (2, 2)), ctx)
    assert calls == ["a", "b", "c"]


def test_each_step_sees_previous_result(ctx):
    result = pipeline(RESIZE, SATURATE).process(Image.new("RGB", (40, 20)), ctx)
    assert result.size == (10, 5)


def test_run_mirrors_subfolders_and_keeps_format(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20))
    make_image("in/sub/deep/b.jpg", size=(20, 40))
    result = pipeline(RESIZE).run(tmp_path / "in", tmp_path / "out", random.Random(1))

    assert len(result.processed) == 2 and not result.skipped
    with Image.open(tmp_path / "out/a.png") as a, Image.open(tmp_path / "out/sub/deep/b.jpg") as b:
        assert (a.format, a.size) == ("PNG", (10, 5))
        assert (b.format, b.size) == ("JPEG", (5, 10))


def test_originals_untouched(make_image, tmp_path):
    source = make_image("in/a.png", size=(40, 20))
    before = source.read_bytes()
    pipeline(RESIZE, SATURATE).run(tmp_path / "in", tmp_path / "out", random.Random(1))
    assert source.read_bytes() == before


def test_unreadable_file_is_skipped_and_batch_continues(make_image, tmp_path):
    make_image("in/a.png")
    (tmp_path / "in/broken.png").write_bytes(b"not an image")
    make_image("in/z.png")
    result = pipeline(RESIZE).run(tmp_path / "in", tmp_path / "out", random.Random(1))

    assert [p.name for p in result.processed] == ["a.png", "z.png"]
    assert [p.name for p, _ in result.skipped] == ["broken.png"]
    assert not (tmp_path / "out/broken.png").exists()


def test_non_image_files_are_ignored(make_image, tmp_path):
    make_image("in/a.png")
    (tmp_path / "in/notes.txt").write_text("hi")
    result = pipeline(RESIZE).run(tmp_path / "in", tmp_path / "out", random.Random(1))
    assert len(result.processed) == 1 and not result.skipped


def test_output_inside_input_is_not_rescanned(make_image, tmp_path):
    make_image("in/a.png")
    pl = pipeline(RESIZE)
    pl.run(tmp_path / "in", tmp_path / "in/out", random.Random(1))
    second = pl.run(tmp_path / "in", tmp_path / "in/out", random.Random(1))
    assert len(second.processed) == 1
    assert not (tmp_path / "in/out/out").exists()


def test_output_equal_to_input_rejected(make_image, tmp_path):
    make_image("in/a.png")
    with pytest.raises(ConfigError, match="must differ"):
        pipeline(RESIZE).run(tmp_path / "in", tmp_path / "in", random.Random(1))


def test_same_seed_same_output(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20), color=(150, 110, 90))
    pl = pipeline(RESIZE, ("rnd_saturation", {"min_percent": 3, "max_percent": 40}))
    pl.run(tmp_path / "in", tmp_path / "o1", random.Random(5))
    pl.run(tmp_path / "in", tmp_path / "o2", random.Random(5))
    assert (tmp_path / "o1/a.png").read_bytes() == (tmp_path / "o2/a.png").read_bytes()


def test_rgba_image_saved_as_jpeg_does_not_fail(tmp_path):
    output.write(
        Image.new("RGBA", (4, 4), (1, 2, 3, 4)), tmp_path / "x.jpg", output.OutputSettings(),
        "JPEG", imageio.Metadata(),
    )
    assert (tmp_path / "x.jpg").exists()


def test_context_is_shared_across_images(make_image, tmp_path):
    make_image("in/a.png", color=(150, 110, 90))
    make_image("in/b.png", color=(150, 110, 90))
    pl = pipeline(("rnd_saturation", {"min_percent": 3, "max_percent": 40}))
    pl.run(tmp_path / "in", tmp_path / "out", random.Random(3))
    assert (tmp_path / "out/a.png").read_bytes() != (tmp_path / "out/b.png").read_bytes()


def test_padding_then_saturation_gives_exact_size(make_image, tmp_path):
    make_image("in/wide.png", size=(60, 20), color=(150, 110, 90))
    make_image("in/tall.png", size=(20, 60), color=(150, 110, 90))
    pl = pipeline(("resize", {"mode": "padding", "size": 30, "fill": "white"}), SATURATE)
    result = pl.run(tmp_path / "in", tmp_path / "out", random.Random(1))

    assert len(result.processed) == 2 and not result.skipped
    for name in ("wide.png", "tall.png"):
        with Image.open(tmp_path / "out" / name) as out:
            assert out.size == (30, 30)


def test_crop_runs_on_jpeg_and_png(make_image, tmp_path):
    make_image("in/a.jpg", size=(60, 20))
    make_image("in/b.png", size=(20, 60))
    pl = pipeline(("resize", {"mode": "crop", "width": 10, "height": 10}))
    pl.run(tmp_path / "in", tmp_path / "out", random.Random(1))
    for name in ("a.jpg", "b.png"):
        with Image.open(tmp_path / "out" / name) as out:
            assert out.size == (10, 10)


def run_with_reports(pl, tmp_path, seed=1):
    reports = []
    result = pl.run(tmp_path / "in", tmp_path / "out", random.Random(seed), on_file=reports.append)
    return result, reports


def test_on_file_reports_each_processed_file_in_order(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20))
    make_image("in/sub/b.png", size=(40, 20))
    _, reports = run_with_reports(pipeline(RESIZE, SATURATE), tmp_path)

    assert [(r.source.as_posix(), r.target.as_posix()) for r in reports] == [
        ("a.png", "a.png"),
        ("sub/b.png", "sub/b.png"),
    ]
    for report in reports:
        assert report.changes == {"size": "40x20 -> 10x5", "saturation": "+20.0%"}
        assert list(report.changes) == ["size", "saturation"]


def test_report_says_when_size_is_unchanged(make_image, tmp_path):
    make_image("in/a.png", size=(5, 5))
    _, reports = run_with_reports(pipeline(RESIZE), tmp_path)
    assert reports[0].changes == {"size": "5x5 (unchanged)"}


def test_resize_only_pipeline_reports_only_size(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20))
    _, reports = run_with_reports(pipeline(RESIZE), tmp_path)
    assert list(reports[0].changes) == ["size"]


def test_repeated_step_changes_are_joined(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20))
    _, reports = run_with_reports(pipeline(SATURATE, SATURATE), tmp_path)
    assert reports[0].changes["saturation"] == "+20.0%, +20.0%"


def test_changes_do_not_leak_between_images(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20))
    make_image("in/b.png", size=(40, 20), mode="L", color=100)
    _, reports = run_with_reports(pipeline(SATURATE), tmp_path)
    assert reports[0].changes["saturation"] == "+20.0%"
    assert reports[1].changes["saturation"] == "n/a (grayscale)"


def test_skipped_file_gets_no_report(make_image, tmp_path):
    make_image("in/a.png")
    (tmp_path / "in/broken.png").write_bytes(b"junk")
    result, reports = run_with_reports(pipeline(RESIZE), tmp_path)
    assert [r.source.name for r in reports] == ["a.png"]
    assert [p.name for p, _ in result.skipped] == ["broken.png"]


# ---------- EXIF orientation ----------

def exif_orientation_of(path):
    with Image.open(path) as image:
        return image.getexif().get(0x0112)


def test_tagged_image_is_made_upright_before_the_steps(make_tagged_image, tmp_path):
    make_tagged_image("in/phone.png", 6, size=(40, 20))  # stored sideways
    result, reports = run_with_reports(pipeline(RESIZE, SATURATE), tmp_path)

    assert not result.skipped
    assert list(reports[0].changes) == ["size", "orientation", "saturation"]
    assert reports[0].changes["size"] == "20x40 -> 5x10"
    assert reports[0].changes["orientation"] == "EXIF (rotated 90° cw)"
    with Image.open(tmp_path / "out/phone.png") as out:
        assert out.size == (5, 10)
        top, bottom = out.getpixel((2, 1)), out.getpixel((2, 8))
        assert top[0] > top[2] and bottom[2] > bottom[0]  # red on top, blue below
    assert exif_orientation_of(tmp_path / "out/phone.png") is None


def test_untagged_and_upright_tagged_images_get_no_orientation_entry(make_image, make_tagged_image, tmp_path):
    make_image("in/a.png", size=(40, 20))
    make_tagged_image("in/b.png", 1, size=(40, 20))
    _, reports = run_with_reports(pipeline(RESIZE), tmp_path)
    assert [list(r.changes) for r in reports] == [["size"], ["size"]]


def test_fix_can_be_switched_off(make_tagged_image, tmp_path):
    make_tagged_image("in/phone.png", 6, size=(40, 20))
    reports = []
    pipeline(RESIZE).run(tmp_path / "in", tmp_path / "out", random.Random(1), reports.append)
    off = Pipeline([create_step(*RESIZE)], fix_orientation=False)
    off_reports = []
    off.run(tmp_path / "in", tmp_path / "out2", random.Random(1), off_reports.append)

    assert reports[0].changes["size"] == "20x40 -> 5x10"
    assert off_reports[0].changes == {"size": "40x20 -> 10x5"}
    with Image.open(tmp_path / "out2/phone.png") as out:
        assert out.size == (10, 5)


@pytest.mark.parametrize("value, words", [(2, "mirrored horizontally"), (3, "rotated 180°")])
def test_non_swapping_orientations_are_reported_too(make_tagged_image, tmp_path, value, words):
    make_tagged_image("in/a.png", value, size=(40, 20))
    _, reports = run_with_reports(pipeline(RESIZE), tmp_path)
    assert reports[0].changes == {"size": "40x20 -> 10x5", "orientation": f"EXIF ({words})"}


def test_orientation_does_not_leak_between_images(make_image, make_tagged_image, tmp_path):
    make_tagged_image("in/a.png", 6)
    make_image("in/b.png", size=(40, 20))
    _, reports = run_with_reports(pipeline(RESIZE), tmp_path)
    assert "orientation" in reports[0].changes and "orientation" not in reports[1].changes


@pytest.mark.parametrize(
    "specs",
    [
        [RESIZE, SATURATE],
        [("resize", {"mode": "crop", "width": 10, "height": 6})],
        [("resize", {"mode": "padding", "size": 12}), SATURATE],
    ],
)
def test_dry_run_reports_equal_real_run_for_tagged_images(make_image, make_tagged_image, tmp_path, specs):
    make_tagged_image("in/a.png", 6)
    make_tagged_image("in/sub/b.png", 8, size=(30, 50))
    make_tagged_image("in/c.png", 3)
    make_image("in/d.png", size=(40, 20))
    pl = pipeline(*specs)
    _, real = run_with_reports(pl, tmp_path)
    dry = []
    pl.run(tmp_path / "in", tmp_path / "dry", random.Random(1), dry.append, dry_run=True)
    assert real and dry == real
