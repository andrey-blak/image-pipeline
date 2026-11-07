import random

import pytest
from PIL import Image

from imgpipe.steps import Context


@pytest.fixture
def make_image(tmp_path):
    """Create a test image file (format taken from the extension); returns its path."""

    def make(relpath, size=(40, 20), mode="RGB", color=(200, 100, 50)):
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new(mode, size, color).save(path)
        return path

    return make


@pytest.fixture
def ctx():
    return Context(rng=random.Random(1))


@pytest.fixture
def make_tagged_image(tmp_path):
    """Create an image file with an EXIF orientation tag (left half red, right half blue)."""

    def make(relpath, orientation, size=(40, 20)):
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", size, (255, 0, 0))
        image.paste((0, 0, 255), (size[0] // 2, 0, size[0], size[1]))
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(path, exif=exif)
        return path

    return make
