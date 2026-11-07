import math

import pytest
from PIL import Image

from imgpipe.rotation import check_corners, inner_scale, quarter_turns, rotate_image

RED = (200, 30, 30)
WHITE = (255, 255, 255)
T = Image.Transpose


def inside_rotated_rect(x, y, width, height, angle, eps=1e-9):
    """Is the point (centered coordinates) inside the width x height rectangle rotated by angle?"""
    a = math.radians(angle)
    rx = x * math.cos(a) + y * math.sin(a)
    ry = -x * math.sin(a) + y * math.cos(a)
    return abs(rx) <= width / 2 + eps and abs(ry) <= height / 2 + eps


def marker_image():
    """3x2 image: the top-left pixel is the marker, all others differ too."""
    image = Image.new("RGB", (3, 2))
    image.putdata([(255, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0), (5, 0, 0)])
    return image


# ---------- quarter turns ----------

@pytest.mark.parametrize(
    "angle, turns",
    [(0, 0), (90, 1), (180, 2), (270, 3), (-90, 3), (-180, 2), (-270, 1), (360, 0), (-720, 0),
     (450, 1), (90 + 1e-12, 1), (89.9, None), (0.001, None), (45, None)],
)
def test_quarter_turns(angle, turns):
    assert quarter_turns(angle) == turns


# ---------- the crop rectangle ----------

SIZES = [(100, 60), (60, 100), (50, 50), (200, 30), (30, 200), (640, 480)]
ANGLES = [0.5, 1, 3.5, 5, 10, 22.5, 30, 44, 45, 60, 80, 89, 120, 150, 179]


def test_scale_is_one_without_rotation():
    assert inner_scale(100, 60, 0) == pytest.approx(1)


@pytest.mark.parametrize("angle", ANGLES)
def test_scale_does_not_depend_on_the_direction_or_whole_half_turns(angle):
    base = inner_scale(100, 60, angle)
    assert inner_scale(100, 60, -angle) == pytest.approx(base)
    assert inner_scale(100, 60, angle + 180) == pytest.approx(base)
    assert inner_scale(100, 60, 180 - angle) == pytest.approx(base)


def test_scale_shrinks_as_the_angle_grows_towards_45():
    scales = [inner_scale(100, 60, a) for a in (0, 2, 5, 10, 20, 30, 45)]
    assert scales == sorted(scales, reverse=True)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("angle", ANGLES)
def test_scaled_rectangle_fits_and_is_the_largest(size, angle):
    width, height = size
    k = inner_scale(width, height, angle)
    assert 0 < k <= 1

    def corners_inside(factor):
        w, h = width * k * factor, height * k * factor
        return all(inside_rotated_rect(sx * w / 2, sy * h / 2, width, height, angle)
                   for sx in (-1, 1) for sy in (-1, 1))

    assert corners_inside(1)
    assert not corners_inside(1.01)


# ---------- check_corners ----------

def test_crop_needs_no_fill_color():
    assert check_corners("crop", None) is None


def test_fill_defaults_to_transparent():
    assert check_corners("fill", None) == (0, 0, 0, 0)


@pytest.mark.parametrize("fill, expected", [("white", (255, 255, 255, 255)), ("#ff0000", (255, 0, 0, 255)),
                                            ("#ff000080", (255, 0, 0, 128))])
def test_fill_colors(fill, expected):
    assert check_corners("fill", fill) == expected


def test_check_corners_errors():
    with pytest.raises(ValueError, match="unknown corners 'zoom'; known values: crop, fill"):
        check_corners("zoom", None)
    with pytest.raises(ValueError, match="option 'fill' is not used by corners 'crop'"):
        check_corners("crop", "white")
    with pytest.raises(ValueError, match="invalid fill color 'nope'"):
        check_corners("fill", "nope")


# ---------- exact turns and directions ----------

@pytest.mark.parametrize(
    "angle, transpose",
    [(90, T.ROTATE_270), (-90, T.ROTATE_90), (270, T.ROTATE_90), (-270, T.ROTATE_270), (180, T.ROTATE_180),
     (-180, T.ROTATE_180), (450, T.ROTATE_270)],
)
@pytest.mark.parametrize("corners, fill", [("crop", None), ("fill", (255, 255, 255, 255))])
def test_exact_turns_are_lossless_transposes(angle, transpose, corners, fill):
    image = marker_image()
    result = rotate_image(image, angle, corners, fill)
    assert result.size == image.transpose(transpose).size
    assert result.tobytes() == image.transpose(transpose).tobytes()


def test_a_positive_angle_turns_clockwise():
    image = marker_image()  # marker in the top-left corner
    assert rotate_image(image, 90, "crop", None).getpixel((1, 0)) == (255, 0, 0)    # top-right
    assert rotate_image(image, 180, "crop", None).getpixel((2, 1)) == (255, 0, 0)   # bottom-right
    assert rotate_image(image, -90, "crop", None).getpixel((0, 2)) == (255, 0, 0)   # bottom-left


@pytest.mark.parametrize("angle", [0, 360, -360, 720])
def test_full_turns_return_the_image_itself(angle):
    image = marker_image()
    assert rotate_image(image, angle, "crop", None) is image


def bar_image():
    image = Image.new("L", (81, 81), 0)
    image.paste(255, (39, 5, 43, 76))  # a vertical bar
    return image


def centroid_x(image, rows):
    xs = [x for y in rows for x in range(image.width) if image.getpixel((x, y)) > 128]
    return sum(xs) / len(xs)


@pytest.mark.parametrize("angle, top_leans", [(10, "right"), (-10, "left")])
def test_small_angles_lean_the_right_way(angle, top_leans):
    result = rotate_image(bar_image(), angle, "fill", (0, 0, 0, 255))
    height = result.height
    top = centroid_x(result, range(height // 4, height // 2 - 2))
    bottom = centroid_x(result, range(height // 2 + 2, 3 * height // 4))
    assert (top > bottom) == (top_leans == "right")


# ---------- crop ----------

@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("angle", ANGLES + [-7, -45, -123, 200, 359])
@pytest.mark.parametrize("mode", ["RGB", "L"])
def test_crop_contains_only_the_content(size, angle, mode):
    color = RED if mode == "RGB" else 120
    base = Image.new(mode, size, color)
    result = rotate_image(base, angle, "crop", None)
    k = inner_scale(*size, angle)
    assert result.size == (max(1, int(size[0] * k) - 2), max(1, int(size[1] * k) - 2))
    assert result.mode == mode
    low, high = result.getextrema() if mode == "L" else tuple(zip(*result.getextrema()))
    reference = (color,) * 2 if mode == "L" else (color, color)
    assert low == pytest.approx(reference[0], abs=2) and high == pytest.approx(reference[1], abs=2)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("angle", [3, 10, 30, 45, -20, 100])
@pytest.mark.parametrize("mode", ["RGBA", "LA"])
def test_crop_of_an_opaque_image_stays_opaque(size, angle, mode):
    base = Image.new(mode, size, (RED + (255,)) if mode == "RGBA" else (120, 255))
    result = rotate_image(base, angle, "crop", None)
    assert result.mode == mode
    assert result.getchannel("A").getextrema()[0] >= 254


def test_crop_keeps_the_aspect_ratio():
    result = rotate_image(Image.new("RGB", (400, 300), RED), 7, "crop", None)
    assert result.width / result.height == pytest.approx(400 / 300, rel=0.02)


def test_crop_of_a_tiny_image_is_never_empty():
    assert min(rotate_image(Image.new("RGB", (3, 3), RED), 45, "crop", None).size) >= 1


def test_crop_result_is_centered_on_the_image_content():
    image = Image.new("RGB", (101, 101), (0, 0, 255))
    image.paste((255, 0, 0), (45, 45, 56, 56))  # a red block in the middle
    result = rotate_image(image, 20, "crop", None)
    center = result.getpixel((result.width // 2, result.height // 2))
    assert center[0] > 200 and center[2] < 60


# ---------- fill ----------

def expanded_size(width, height, angle):
    a = math.radians(abs(angle))
    return width * abs(math.cos(a)) + height * abs(math.sin(a)), width * abs(math.sin(a)) + height * abs(math.cos(a))


@pytest.mark.parametrize("angle", [5, -5, 17, 45, 100])
def test_fill_grows_the_canvas_to_hold_everything(angle):
    image = Image.new("RGB", (100, 60), RED)
    result = rotate_image(image, angle, "fill", (255, 255, 255, 255))
    width, height = expanded_size(100, 60, angle)
    assert abs(result.width - width) <= 2 and abs(result.height - height) <= 2
    assert result.width * result.height >= 100 * 60  # nothing is cut off


def test_opaque_fill_on_rgb_fills_the_corners_and_keeps_the_picture():
    image = Image.new("RGB", (100, 60), RED)
    result = rotate_image(image, 20, "fill", (255, 255, 255, 255))
    assert result.mode == "RGB"
    for xy in [(0, 0), (result.width - 1, 0), (0, result.height - 1), (result.width - 1, result.height - 1)]:
        assert result.getpixel(xy) == WHITE
    assert result.getpixel((result.width // 2, result.height // 2)) == RED


def test_transparent_fill_gives_rgba_with_transparent_corners():
    result = rotate_image(Image.new("RGB", (100, 60), RED), 20, "fill", (0, 0, 0, 0))
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((result.width // 2, result.height // 2)) == RED + (255,)


@pytest.mark.parametrize("angle", [3, 11, 30, 45])
def test_no_dark_fringe_around_a_light_picture(angle):
    result = rotate_image(Image.new("RGBA", (80, 50), WHITE + (255,)), angle, "fill", (0, 0, 0, 0))
    visible = [result.getpixel((x, y)) for x in range(result.width) for y in range(result.height)
               if result.getpixel((x, y))[3] > 0]
    assert visible and all(min(p[:3]) >= 250 for p in visible)


def test_soft_alpha_inside_the_picture_does_not_darken_the_colors():
    image = Image.new("RGBA", (60, 60), WHITE + (255,))
    image.paste((0, 0, 0, 0), (20, 20, 40, 40))  # a transparent hole with black hidden RGB
    result = rotate_image(image, 15, "fill", (0, 0, 0, 0))
    soft = [result.getpixel((x, y)) for x in range(result.width) for y in range(result.height)
            if 0 < result.getpixel((x, y))[3] < 255]
    assert soft and all(min(p[:3]) >= 250 for p in soft)


def test_opaque_fill_keeps_transparency_that_the_source_had():
    image = Image.new("RGBA", (60, 60), RED + (255,))
    image.paste((0, 0, 0, 0), (25, 25, 35, 35))
    result = rotate_image(image, 15, "fill", (255, 255, 255, 255))
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0)) == WHITE + (255,)
    assert result.getpixel((result.width // 2, result.height // 2))[3] == 0
    assert result.getpixel((result.width // 2 + 14, result.height // 2)) == RED + (255,)


def test_partly_transparent_fill_color():
    result = rotate_image(Image.new("RGB", (60, 40), WHITE), 20, "fill", (255, 0, 0, 128))
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0)) == (255, 0, 0, 128)


def test_gray_images_with_a_gray_fill_stay_gray():
    result = rotate_image(Image.new("L", (60, 40), 200), 20, "fill", (128, 128, 128, 255))
    assert result.mode == "L" and result.getpixel((0, 0)) == 128


def test_gray_images_with_a_colored_fill_become_rgb():
    result = rotate_image(Image.new("L", (60, 40), 200), 20, "fill", (255, 0, 0, 255))
    assert result.mode == "RGB" and result.getpixel((0, 0)) == (255, 0, 0)


def test_gray_with_alpha_and_transparent_fill():
    result = rotate_image(Image.new("LA", (60, 40), (200, 255)), 20, "fill", (0, 0, 0, 0))
    assert result.mode == "RGBA" and result.getpixel((0, 0))[3] == 0


def test_input_image_is_not_modified():
    image = Image.new("RGBA", (50, 30), RED + (255,))
    before = image.tobytes()
    for corners, fill in [("crop", None), ("fill", (0, 0, 0, 0)), ("fill", (255, 255, 255, 255))]:
        rotate_image(image, 12, corners, fill)
    assert image.tobytes() == before and image.size == (50, 30)
