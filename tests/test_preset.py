import pytest

from imgpipe.preset import load_preset
from imgpipe.errors import PresetError


def write(tmp_path, text):
    path = tmp_path / "preset.toml"
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
    steps = load_preset(path).steps
    assert [s.name for s in steps] == ["rnd_saturation", "resize"]
    assert steps[1].size == 300
    assert steps[1].mode == "longest_side"


def test_missing_file(tmp_path):
    with pytest.raises(PresetError, match="preset file not found"):
        load_preset(tmp_path / "missing.toml")


def test_invalid_toml(tmp_path):
    with pytest.raises(PresetError, match="invalid TOML"):
        load_preset(write(tmp_path, "[[steps"))


def test_no_steps(tmp_path):
    with pytest.raises(PresetError, match="at least one"):
        load_preset(write(tmp_path, ""))


def test_step_without_name(tmp_path):
    with pytest.raises(PresetError, match=r"#1 needs a 'name'"):
        load_preset(write(tmp_path, "[[steps]]\nsize = 3\n"))


def test_unknown_top_level_key(tmp_path):
    with pytest.raises(PresetError, match="unknown top-level key.*stepz"):
        load_preset(write(tmp_path, '[[stepz]]\nname = "resize"\n'))


def test_step_errors_propagate(tmp_path):
    with pytest.raises(PresetError, match="unknown step 'sharpen'"):
        load_preset(write(tmp_path, '[[steps]]\nname = "sharpen"\n'))


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
    (step,) = load_preset(path).steps
    assert (step.mode, step.width, step.height, step.fill, step.upscale) == (
        "padding", 300, 200, "#ffffff", True
    )


def test_resize_invalid_mode_options_reported_with_step_name(tmp_path):
    path = write(tmp_path, '[[steps]]\nname = "resize"\nmode = "crop"\nwidth = 5\n')
    with pytest.raises(PresetError, match="step 'resize': mode 'crop' needs"):
        load_preset(path)


# ---------- [options] section ----------

STEP = '[[steps]]\nname = "resize"\nsize = 10\n'
OPTIONS_OFF = "[options]\nfix_orientation = false\n"


def test_fix_orientation_defaults_to_true(tmp_path):
    assert load_preset(write(tmp_path, STEP)).fix_orientation is True


@pytest.mark.parametrize("value", ["true", "false"])
def test_fix_orientation_can_be_set(tmp_path, value):
    preset = load_preset(write(tmp_path, f"{STEP}\n[options]\nfix_orientation = {value}\n"))
    assert preset.fix_orientation is (value == "true")
    assert [s.name for s in preset.steps] == ["resize"]


def test_options_section_may_come_before_or_after_the_steps(tmp_path):
    before = load_preset(write(tmp_path, f"{OPTIONS_OFF}\n{STEP}"))
    after = load_preset(write(tmp_path, f"{STEP}\n{OPTIONS_OFF}"))
    assert before.fix_orientation is False and after.fix_orientation is False
    assert [s.name for s in before.steps] == [s.name for s in after.steps] == ["resize"]


def test_options_section_between_steps(tmp_path):
    text = f'{STEP}\n{OPTIONS_OFF}\n[[steps]]\nname = "rnd_saturation"\nmin_percent = 1\nmax_percent = 2\n'
    preset = load_preset(write(tmp_path, text))
    assert preset.fix_orientation is False
    assert [s.name for s in preset.steps] == ["resize", "rnd_saturation"]


def test_empty_options_section_is_fine(tmp_path):
    assert load_preset(write(tmp_path, f"[options]\n{STEP}")).fix_orientation is True


@pytest.mark.parametrize("value", ['"yes"', "1", "0.5"])
def test_fix_orientation_must_be_a_bool(tmp_path, value):
    with pytest.raises(PresetError, match="option 'fix_orientation' must be bool"):
        load_preset(write(tmp_path, f"{STEP}\n[options]\nfix_orientation = {value}\n"))


def test_unknown_option_lists_the_known_ones(tmp_path):
    with pytest.raises(PresetError, match=r"unknown option\(s\) fix_orient in \[options\]; known options: fix_orientation"):
        load_preset(write(tmp_path, f"{STEP}\n[options]\nfix_orient = true\n"))


@pytest.mark.parametrize("text", ["options = 1\n", "options = [1]\n", '[[options]]\nfix_orientation = true\n'])
def test_options_must_be_a_section(tmp_path, text):
    with pytest.raises(PresetError, match=r"\[options\] must be a section"):
        load_preset(write(tmp_path, f"{STEP}\n{text}" if text.startswith("[[") else f"{text}\n{STEP}"))


def test_old_top_level_form_gets_a_hint(tmp_path):
    with pytest.raises(PresetError, match=r"option 'fix_orientation' belongs in the \[options\] section"):
        load_preset(write(tmp_path, f"fix_orientation = true\n{STEP}"))


def test_bare_key_after_a_step_belongs_to_that_step(tmp_path):
    with pytest.raises(PresetError, match="step 'resize': unknown option.*fix_orientation"):
        load_preset(write(tmp_path, f"{STEP}fix_orientation = false\n"))


def test_other_top_level_keys_still_rejected(tmp_path):
    with pytest.raises(PresetError, match="unknown top-level key.*option"):
        load_preset(write(tmp_path, f"option = true\n{STEP}"))


def test_options_alone_are_not_enough(tmp_path):
    with pytest.raises(PresetError, match="at least one"):
        load_preset(write(tmp_path, OPTIONS_OFF))


# ---------- [output] section ----------

from imgpipe.output import OutputSettings  # noqa: E402


def test_output_defaults(tmp_path):
    assert load_preset(write(tmp_path, STEP)).output == OutputSettings()


def test_output_values_are_loaded(tmp_path):
    text = f'{STEP}\n[output]\nformat = "jpeg"\nquality = 80\nbackground = "#102030"\nkeep_metadata = true\n'
    output = load_preset(write(tmp_path, text)).output
    assert (output.format, output.quality, output.background, output.keep_metadata) == ("jpg", 80, "#102030", True)


def test_output_section_may_come_before_or_after_the_steps(tmp_path):
    section = '[output]\nformat = "webp"\n'
    assert load_preset(write(tmp_path, f"{section}\n{STEP}")).output.format == "webp"
    assert load_preset(write(tmp_path, f"{STEP}\n{section}")).output.format == "webp"


def test_output_and_options_tables_are_independent(tmp_path):
    preset = load_preset(write(tmp_path, f'{STEP}\n[output]\nformat = "png"\n\n{OPTIONS_OFF}'))
    assert preset.output.format == "png" and preset.fix_orientation is False


def test_unknown_output_option_lists_the_known_ones(tmp_path):
    with pytest.raises(PresetError, match=r"unknown option\(s\) colour in \[output\]; known options: format, quality, background, keep_metadata"):
        load_preset(write(tmp_path, f'{STEP}\n[output]\ncolour = "x"\n'))


@pytest.mark.parametrize(
    "line, message",
    [
        ("format = 5", "option 'format' must be str"),
        ('quality = "90"', "option 'quality' must be int"),
        ("quality = 90.5", "option 'quality' must be int"),
        ("quality = true", "option 'quality' must be int"),
        ("background = 1", "option 'background' must be str"),
        ('keep_metadata = "yes"', "option 'keep_metadata' must be bool"),
    ],
)
def test_output_option_types(tmp_path, line, message):
    with pytest.raises(PresetError, match=message):
        load_preset(write(tmp_path, f"{STEP}\n[output]\n{line}\n"))


@pytest.mark.parametrize(
    "lines, message",
    [
        ('format = "heic"', r"\[output\]: unknown format 'heic'"),
        ("quality = 0", r"\[output\]: 'quality' must be between 1 and 100"),
        ('format = "png"\nquality = 80', r"\[output\]: option 'quality' is not used by format 'png'"),
        ('background = "transparent"', r"\[output\]: 'background' must be an opaque color"),
        ('background = "nope"', r"\[output\]: invalid background color 'nope'"),
    ],
)
def test_invalid_output_values(tmp_path, lines, message):
    with pytest.raises(PresetError, match=message):
        load_preset(write(tmp_path, f"{STEP}\n[output]\n{lines}\n"))


def test_output_key_at_the_top_level_gets_a_hint(tmp_path):
    with pytest.raises(PresetError, match=r"option 'format' belongs in the \[output\] section"):
        load_preset(write(tmp_path, f'format = "jpg"\n{STEP}'))


@pytest.mark.parametrize("text", ["output = 1\n", "output = [1]\n"])
def test_output_must_be_a_section(tmp_path, text):
    with pytest.raises(PresetError, match=r"\[output\] must be a section"):
        load_preset(write(tmp_path, f"{text}\n{STEP}"))


# ---------- runs without steps ----------

CHANGES_FILES = [
    '[output]\nformat = "webp"',
    '[output]\nformat = "jpeg"',
    '[output]\nquality = 80',
    '[output]\nkeep_metadata = false',
    '[options]\nfix_orientation = true',
    '[rename]\npattern = "N"',
]
CHANGES_NOTHING = [
    "",
    "[output]",
    "[options]",
    '[output]\nformat = "keep"',
    "[output]\nkeep_metadata = true",
    '[output]\nbackground = "red"',
    "[options]\nfix_orientation = false",
]


@pytest.mark.parametrize("text", CHANGES_FILES)
@pytest.mark.parametrize("steps_line", ["", "steps = []\n"])
def test_no_steps_needed_when_the_global_tables_change_files(tmp_path, text, steps_line):
    path = write(tmp_path, f"{steps_line}{text}\n")
    assert load_preset(path).steps == []


@pytest.mark.parametrize("text", CHANGES_NOTHING)
@pytest.mark.parametrize("steps_line", ["", "steps = []\n"])
def test_no_steps_and_nothing_changed_keeps_the_error(tmp_path, text, steps_line):
    with pytest.raises(PresetError, match=r"define at least one \[\[steps\]\] entry"):
        load_preset(write(tmp_path, f"{steps_line}{text}\n"))


def test_steps_are_kept_next_to_a_file_changing_section(tmp_path):
    preset = load_preset(write(tmp_path, f'[output]\nformat = "png"\n{STEP}'))
    assert [s.name for s in preset.steps] == ["resize"]
