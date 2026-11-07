from pathlib import Path

from PIL import Image

IMAGE_EXTENSIONS = frozenset(
    ext for ext, fmt in Image.registered_extensions().items() if fmt in Image.OPEN
)


def find_images(input_dir: Path, exclude: Path | None = None) -> list[Path]:
    """Image files under ``input_dir`` (recursive, sorted), skipping the ``exclude`` folder."""
    found = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if exclude is not None and path.resolve().is_relative_to(exclude):
            continue
        found.append(path)
    return found


EXIF_ORIENTATION_TAG = 0x0112

# EXIF orientation value -> (transpose that makes the stored image upright, description).
# Value 1 (already upright) and anything else need no change. Same operations as
# `PIL.ImageOps.exif_transpose`.
ORIENTATIONS = {
    2: (Image.Transpose.FLIP_LEFT_RIGHT, "mirrored horizontally"),
    3: (Image.Transpose.ROTATE_180, "rotated 180°"),
    4: (Image.Transpose.FLIP_TOP_BOTTOM, "mirrored vertically"),
    5: (Image.Transpose.TRANSPOSE, "transposed"),
    6: (Image.Transpose.ROTATE_270, "rotated 90° cw"),
    7: (Image.Transpose.TRANSVERSE, "anti-transposed"),
    8: (Image.Transpose.ROTATE_90, "rotated 90° ccw"),
}


def load(path: Path) -> tuple[Image.Image, str, int | None]:
    """Open and fully read an image; returns it with its original format and EXIF orientation."""
    with Image.open(path) as opened:
        fmt = opened.format
        try:
            orientation = opened.getexif().get(EXIF_ORIENTATION_TAG)
        except Exception:  # damaged EXIF data must not make the image unreadable
            orientation = None
        opened.load()
        return opened.copy(), fmt, orientation


def fix_orientation(image: Image.Image, orientation: int | None) -> tuple[Image.Image, str | None]:
    """Make the image upright according to its EXIF orientation.

    Returns the image and a description of what was done, or the image itself and
    ``None`` when the orientation is missing, already upright, or not a known value.
    """
    if not isinstance(orientation, int) or orientation not in ORIENTATIONS:
        return image, None
    transpose, description = ORIENTATIONS[orientation]
    return image.transpose(transpose), description


def save(image: Image.Image, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(path, format=fmt)
