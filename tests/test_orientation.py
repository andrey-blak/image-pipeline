import random

import pytest
from PIL import Image, ImageOps

from imgpipe import imageio
from imgpipe.pipeline import Pipeline
from imgpipe.steps import Context, create_step
from imgpipe.steps.resize import Resize
from imgpipe.steps.rnd_rotate import RandomRotate
from imgpipe.steps.rotate import Rotate

T = Image.Transpose
# Applying this to an upright image gives the way it is stored for each EXIF value.
STORE = {
    2: T.FLIP_LEFT_RIGHT,
    3: T.ROTATE_180,
    4: T.FLIP_TOP_BOTTOM,
    5: T.TRANSPOSE,
    6: T.ROTATE_90,
    7: T.TRANSVERSE,
    8: T.ROTATE_270,
}


def upright():
    image = Image.new("RGB", (3, 2))
    image.putdata([(10, 0, 0), (20, 0, 0), (30, 0, 0), (0, 10, 0), (0, 20, 0), (0, 30, 0)])
    return image


def save_tagged(path, image, value):
    exif = Image.Exif()
    exif[0x0112] = value
    image.save(path, exif=exif)
    return path


@pytest.mark.parametrize("value", sorted(STORE))
def test_fix_makes_the_stored_image_upright(tmp_path, value):
    path = save_tagged(tmp_path / "x.png", upright().transpose(STORE[value]), value)

    image, fmt, orientation, _ = imageio.load(path)
    fixed, description = imageio.fix_orientation(image, orientation)

    assert (fmt, orientation) == ("PNG", value)
    assert description
    assert fixed.size == (3, 2) and fixed.tobytes() == upright().tobytes()


@pytest.mark.parametrize("value", sorted(STORE))
def test_fix_matches_pillows_own_exif_transpose(tmp_path, value):
    path = save_tagged(tmp_path / "x.png", upright().transpose(STORE[value]), value)
    image, _, orientation, _ = imageio.load(path)
    fixed, _ = imageio.fix_orientation(image, orientation)
    with Image.open(path) as opened:
        expected = ImageOps.exif_transpose(opened)
    assert fixed.size == expected.size and fixed.tobytes() == expected.tobytes()


@pytest.mark.parametrize(
    "value, words",
    [
        (2, "mirrored horizontally"),
        (3, "rotated 180°"),
        (4, "mirrored vertically"),
        (5, "transposed"),
        (6, "rotated 90° cw"),
        (7, "anti-transposed"),
        (8, "rotated 90° ccw"),
    ],
)
def test_descriptions(value, words):
    assert imageio.fix_orientation(upright(), value)[1] == words


def test_load_reads_the_tag_from_jpeg(tmp_path):
    path = save_tagged(tmp_path / "x.jpg", Image.new("RGB", (8, 4)), 6)
    assert imageio.load(path)[2] == 6


def test_load_gives_none_without_a_tag(tmp_path):
    Image.new("RGB", (8, 4)).save(tmp_path / "x.png")
    Image.new("RGB", (8, 4)).save(tmp_path / "x.jpg")
    assert imageio.load(tmp_path / "x.png")[2] is None
    assert imageio.load(tmp_path / "x.jpg")[2] is None


@pytest.mark.parametrize("value", [None, 1, 0, 9, "6", 6.0, (6,)])
def test_unknown_or_upright_values_change_nothing(value):
    image = upright()
    result, description = imageio.fix_orientation(image, value)
    assert result is image and description is None


def test_damaged_exif_does_not_make_the_image_unreadable(tmp_path):
    path = tmp_path / "x.jpg"
    Image.new("RGB", (8, 4)).save(path, exif=b"Exif\x00\x00not really exif data")
    image, fmt, orientation, _ = imageio.load(path)
    assert image.size == (8, 4) and fmt == "JPEG" and orientation is None


# ---------- steps see the photo as shown when the orientation is kept ----------

def kept(orientation):
    return Context(rng=random.Random(1), orientation=orientation)


@pytest.mark.parametrize("value, swaps, mirrored", [
    (None, False, False), (1, False, False), (2, False, True), (3, False, False), (4, False, True),
    (5, True, True), (6, True, False), (7, True, True), (8, True, False),
])
def test_context_knows_how_the_stored_image_is_shown(value, swaps, mirrored):
    ctx = kept(value)
    assert (ctx.swaps_axes, ctx.mirrored) == (swaps, mirrored)


@pytest.mark.parametrize("value, expected", [(None, (10, 5)), (3, (10, 5)), (6, (20, 10)), (8, (20, 10))])
def test_resize_width_refers_to_the_shown_photo(value, expected):
    # stored 40x20; the swapping values show it as 20x40, and width 10 means the shown width
    result = Resize(mode="scale", width=10).apply(Image.new("RGB", (40, 20)), kept(value))
    assert result.size == expected


def test_resize_height_refers_to_the_shown_photo():
    result = Resize(mode="scale", height=10).apply(Image.new("RGB", (40, 20)), kept(6))
    assert result.size == (10, 5)  # shown 5x10


@pytest.mark.parametrize("mode", ["padding", "crop"])
def test_fixed_size_canvas_is_in_the_shown_frame(mode):
    result = Resize(mode=mode, width=100, height=60).apply(Image.new("RGB", (40, 20)), kept(6))
    assert result.size == (60, 100)  # shown as 100x60
    plain = Resize(mode=mode, width=100, height=60).apply(Image.new("RGB", (40, 20)), kept(None))
    assert plain.size == (100, 60)


def test_resize_size_report_is_the_same_in_a_dry_run():
    step = Resize(mode="scale", width=10)
    ctx = kept(6)
    ctx.skip_pixels = ctx.skip_resize = True
    step.apply(Image.new("RGB", (40, 20)), ctx)
    assert ctx.reported_size == (20, 10)


def bands_image():
    image = Image.new("RGB", (30, 20), (255, 0, 0))
    image.paste((0, 0, 255), (15, 0, 30, 20))
    return image


@pytest.mark.parametrize("value", [2, 4, 5, 7])
def test_rotate_turns_the_shown_photo_the_same_way_for_mirrored_tags(value):
    plain = Rotate(angle=90).apply(bands_image(), kept(None))
    mirrored = Rotate(angle=90).apply(bands_image(), kept(value))
    assert mirrored.tobytes() == Rotate(angle=-90).apply(bands_image(), kept(None)).tobytes()
    assert mirrored.tobytes() != plain.tobytes()


@pytest.mark.parametrize("value", [3, 6, 8])
def test_rotate_is_unchanged_for_turned_tags(value):
    plain = Rotate(angle=90).apply(bands_image(), kept(None))
    assert Rotate(angle=90).apply(bands_image(), kept(value)).tobytes() == plain.tobytes()


def test_random_rotation_goes_the_other_way_for_mirrored_tags():
    step = RandomRotate(min_angle=15, max_angle=15)
    plain_ctx, mirrored_ctx = kept(None), kept(2)
    plain_ctx.rng, mirrored_ctx.rng = random.Random(7), random.Random(7)
    plain = step.apply(bands_image(), plain_ctx)
    mirrored = step.apply(bands_image(), mirrored_ctx)
    assert plain_ctx.changes == mirrored_ctx.changes  # the reported angle is the shown one
    angle = float(plain_ctx.changes["rotation"].rstrip("°"))
    assert plain.tobytes() == Rotate(angle=angle).apply(bands_image(), kept(None)).tobytes()
    assert mirrored.tobytes() == Rotate(angle=-angle).apply(bands_image(), kept(None)).tobytes()


def test_keep_mode_end_to_end(make_tagged_image, tmp_path):
    make_tagged_image("in/phone.jpg", 6, size=(40, 20))
    pipeline = Pipeline([create_step("resize", {"mode": "scale", "width": 10})], "keep")
    pipeline.run(tmp_path / "in", tmp_path / "out", random.Random(1))
    with Image.open(tmp_path / "out/phone.jpg") as out:
        assert out.size == (20, 10) and out.getexif()[0x0112] == 6  # shown as 10x20


@pytest.mark.parametrize("value", [1, 3, 6, 8])
def test_keep_mode_dry_run_matches_the_real_run(make_tagged_image, tmp_path, value):
    make_tagged_image("in/phone.jpg", value, size=(40, 20))
    pipeline = Pipeline([create_step("resize", {"mode": "padding", "width": 30, "height": 20})], "keep")
    dry, real = [], []
    pipeline.run(tmp_path / "in", tmp_path / "o1", random.Random(1), dry.append, dry_run=True)
    pipeline.run(tmp_path / "in", tmp_path / "o2", random.Random(1), real.append)
    assert dry == real
