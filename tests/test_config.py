import pytest

from imgpipe.config import load_steps
from imgpipe.errors import ConfigError


def write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_steps_loaded_in_file_order(tmp_path):
    path = write(
        tmp_path,
        """
[[steps]]
name = "rnd_saturation"
min_percent = 3
max_percent = 5

[[steps]]
name = "resize"
size = 300
""",
    )
    steps = load_steps(path)
    assert [s.name for s in steps] == ["rnd_saturation", "resize"]
    assert steps[1].size == 300
    assert steps[1].mode == "longest_side"


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="config file not found"):
        load_steps(tmp_path / "missing.toml")


def test_invalid_toml(tmp_path):
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_steps(write(tmp_path, "[[steps"))


def test_no_steps(tmp_path):
    with pytest.raises(ConfigError, match="at least one"):
        load_steps(write(tmp_path, ""))


def test_step_without_name(tmp_path):
    with pytest.raises(ConfigError, match=r"#1 needs a 'name'"):
        load_steps(write(tmp_path, "[[steps]]\nsize = 3\n"))


def test_unknown_top_level_key(tmp_path):
    with pytest.raises(ConfigError, match="unknown top-level key.*stepz"):
        load_steps(write(tmp_path, '[[stepz]]\nname = "resize"\n'))


def test_step_errors_propagate(tmp_path):
    with pytest.raises(ConfigError, match="unknown step 'rotate'"):
        load_steps(write(tmp_path, '[[steps]]\nname = "rotate"\n'))


def test_resize_padding_options_loaded(tmp_path):
    path = write(
        tmp_path,
        """
[[steps]]
name = "resize"
mode = "padding"
width = 300
height = 200
fill = "#ffffff"
upscale = true
""",
    )
    (step,) = load_steps(path)
    assert (step.mode, step.width, step.height, step.fill, step.upscale) == (
        "padding", 300, 200, "#ffffff", True
    )


def test_resize_invalid_mode_options_reported_with_step_name(tmp_path):
    path = write(tmp_path, '[[steps]]\nname = "resize"\nmode = "crop"\nwidth = 5\n')
    with pytest.raises(ConfigError, match="step 'resize': mode 'crop' needs"):
        load_steps(path)
