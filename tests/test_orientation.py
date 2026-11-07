import pytest
from PIL import Image, ImageOps

from imgpipe import imageio

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
