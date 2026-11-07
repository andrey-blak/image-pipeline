from pathlib import Path
from typing import NamedTuple

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

# What to do with the EXIF orientation of a photo (the `exif_orientation` option):
# apply  - rotate the pixels upright and drop the tag (it would rotate the photo twice)
# keep   - leave the pixels as stored; the tag stays where metadata is kept
# remove - leave the pixels as stored and drop the tag
EXIF_ORIENTATION_MODES = ("apply", "keep", "remove")

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


ORIENTATION_VALUES = frozenset({1, *ORIENTATIONS})


class Metadata(NamedTuple):
    """Metadata of a source image that can be carried over to the output (see ``output.write``)."""

    exif: bytes | None = None
    xmp: bytes | None = None
    icc_profile: bytes | None = None
    comment: bytes | None = None


class Loaded(NamedTuple):
    image: Image.Image
    format: str
    orientation: int | None
    metadata: Metadata


def _as_bytes(value) -> bytes | None:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return value or None


def load(path: Path) -> Loaded:
    """Open and fully read an image; returns it with its format, EXIF orientation and metadata."""
    with Image.open(path) as opened:
        opened.load()
        fmt = opened.format
        orientation = exif_bytes = None
        try:
            exif = opened.getexif()
            orientation = exif.get(EXIF_ORIENTATION_TAG)
            exif_bytes = exif.tobytes() if len(exif) else None
        except Exception:  # damaged EXIF data must not make the image unreadable
            pass
        info = opened.info
        metadata = Metadata(
            exif=exif_bytes,
            xmp=_as_bytes(info.get("xmp") or info.get("XML:com.adobe.xmp")),
            icc_profile=_as_bytes(info.get("icc_profile")),
            comment=_as_bytes(info.get("comment")),
        )
        return Loaded(opened.copy(), fmt, orientation, metadata)


def fix_orientation(image: Image.Image, orientation: int | None) -> tuple[Image.Image, str | None]:
    """Make the image upright according to its EXIF orientation.

    Returns the image and a description of what was done, or the image itself and
    ``None`` when the orientation is missing, already upright, or not a known value.
    """
    if not isinstance(orientation, int) or orientation not in ORIENTATIONS:
        return image, None
    transpose, description = ORIENTATIONS[orientation]
    return image.transpose(transpose), description
