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


def load(path: Path) -> tuple[Image.Image, str]:
    """Open and fully read an image; returns it with its original format."""
    with Image.open(path) as opened:
        fmt = opened.format
        opened.load()
        return opened.copy(), fmt


def save(image: Image.Image, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(path, format=fmt)
