"""Smoke tests for a built standalone executable.

Skipped unless IMGPIPE_BIN points at the executable (see packaging/build.py).
"""

import os
import subprocess

import pytest
from PIL import Image

BIN = os.environ.get("IMGPIPE_BIN")
pytestmark = pytest.mark.skipif(not BIN, reason="IMGPIPE_BIN not set")

PRESET = """
[[steps]]
name = "resize"
size = 10

[output]
format = "webp"
"""


def run(*args):
    return subprocess.run([BIN, *map(str, args)], capture_output=True, text=True, timeout=120)


def test_help():
    result = run("--help")
    assert result.returncode == 0
    assert "--preset" in result.stdout


def test_real_run_and_dry_run(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20), color=(150, 110, 90))
    preset = tmp_path / "preset.toml"
    preset.write_text(PRESET)
    common = ["--preset", preset, "--input", tmp_path / "in", "--output", tmp_path / "out", "--seed", 1]

    dry = run(*common, "-n", "--verbose")
    assert dry.returncode == 0, dry.stderr
    assert not (tmp_path / "out").exists()

    real = run(*common, "--verbose")
    assert real.returncode == 0, real.stderr
    with Image.open(tmp_path / "out/a.webp") as img:
        assert img.size == (10, 5)
