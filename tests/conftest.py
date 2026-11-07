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
