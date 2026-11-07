import re

import pytest
from pathlib import Path

from PIL import Image

from imgpipe.cli import format_report, main
from imgpipe.pipeline import FileReport

PRESET = """
[[steps]]
name = "resize"
size = 10

[[steps]]
name = "rnd_saturation"
min_percent = 3
max_percent = 40
"""


def setup(make_image, tmp_path):
    make_image("in/a.png", size=(40, 20), color=(150, 110, 90))
    make_image("in/sub/b.jpg", size=(20, 40), color=(150, 110, 90))
    preset = tmp_path / "preset.toml"
    preset.write_text(PRESET)
    return preset


def test_end_to_end(make_image, tmp_path, capsys):
    preset = setup(make_image, tmp_path)
    code = main(["--preset", str(preset), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out"), "--seed", "1"])

    assert code == 0
    assert "2 images processed, 0 skipped." in capsys.readouterr().out
    with Image.open(tmp_path / "out/a.png") as a, Image.open(tmp_path / "out/sub/b.jpg") as b:
        assert a.size == (10, 5)
        assert b.size == (5, 10)


def test_same_seed_twice_gives_identical_output(make_image, tmp_path):
    preset = setup(make_image, tmp_path)
    for out in ("o1", "o2"):
        main(["--preset", str(preset), "--input", str(tmp_path / "in"),
              "--output", str(tmp_path / out), "--seed", "9"])
    for rel in ("a.png", "sub/b.jpg"):
        assert (tmp_path / "o1" / rel).read_bytes() == (tmp_path / "o2" / rel).read_bytes()


def test_no_preset_does_nothing(make_image, tmp_path, capsys):
    make_image("in/a.png")
    code = main(["--input", str(tmp_path / "in"), "--output", str(tmp_path / "out")])

    assert code == 0
    assert "nothing to do" in capsys.readouterr().out.lower()
    assert not (tmp_path / "out").exists()


def test_bad_preset_reports_error(tmp_path, capsys):
    preset = tmp_path / "preset.toml"
    preset.write_text('[[steps]]\nname = "nope"\n')
    code = main(["--preset", str(preset), "--input", str(tmp_path)])

    assert code == 2
    assert "error: unknown step 'nope'" in capsys.readouterr().err


def test_missing_input_folder(tmp_path, capsys):
    preset = tmp_path / "preset.toml"
    preset.write_text(PRESET)
    code = main(["--preset", str(preset), "--input", str(tmp_path / "nope")])

    assert code == 2
    assert "input folder not found" in capsys.readouterr().err


def test_bad_file_gives_warning_and_exit_zero(make_image, tmp_path, capsys):
    preset = setup(make_image, tmp_path)
    (tmp_path / "in/broken.png").write_bytes(b"junk")
    code = main(["--preset", str(preset), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out")])

    captured = capsys.readouterr()
    assert code == 0
    assert "warning: skipped" in captured.err and "broken.png" in captured.err
    assert "2 images processed, 1 skipped." in captured.out


def run_verbose(tmp_path, seed="1"):
    return main(["--preset", str(tmp_path / "preset.toml"), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out"), "--seed", seed, "--verbose"])


def test_verbose_lists_each_file(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    assert run_verbose(tmp_path) == 0

    lines = capsys.readouterr().out.splitlines()
    pattern = r"{src} -> {dst} \| size {old} -> {new} \| saturation [+-]\d+\.\d%"
    for line, (rel, old, new) in zip(lines, [("a.png", "40x20", "10x5"), ("sub/b.jpg", "20x40", "5x10")]):
        assert re.fullmatch(
            pattern.format(src=re.escape(str(tmp_path / "in" / rel)), dst=re.escape(str(tmp_path / "out" / rel)),
                           old=old, new=new),
            line,
        )
    assert lines[-1] == "2 images processed, 0 skipped."
    assert len(lines) == 3


def test_one_progress_line_per_file_without_details_by_default(make_image, tmp_path, capsys):
    preset = setup(make_image, tmp_path)
    main(["--preset", str(preset), "--input", str(tmp_path / "in"), "--output", str(tmp_path / "out")])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3 and lines[-1] == "2 images processed, 0 skipped."
    assert lines[0] == f"{tmp_path / 'in/a.png'} -> {tmp_path / 'out/a.png'}"
    assert lines[1] == f"{tmp_path / 'in/sub/b.jpg'} -> {tmp_path / 'out/sub/b.jpg'}"


def test_verbose_adds_the_details_to_the_progress_lines(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    run_cli(tmp_path)
    plain = capsys.readouterr().out.splitlines()
    run_cli(tmp_path, "-v")
    verbose = capsys.readouterr().out.splitlines()
    assert [line.split(" | ")[0] for line in verbose[:2]] == plain[:2]
    assert all(" | size " in line for line in verbose[:2]) and not any(" | " in line for line in plain)


@pytest.mark.parametrize("flag", ["-q", "--quiet"])
def test_quiet_prints_no_progress_and_no_summary(make_image, tmp_path, capsys, flag):
    setup(make_image, tmp_path)
    assert run_cli(tmp_path, flag) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert (tmp_path / "out/a.png").exists()


def test_quiet_still_shows_warnings_and_errors(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    (tmp_path / "in/broken.png").write_bytes(b"not an image")
    assert run_cli(tmp_path, "-q") == 0
    captured = capsys.readouterr()
    assert captured.out == "" and "warning: skipped" in captured.err and "broken.png" in captured.err

    (tmp_path / "preset.toml").write_text("")
    assert run_cli(tmp_path, "-q") == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("other", ["-v", "-n"])
def test_quiet_cannot_be_combined_with_verbose_or_dry_run(tmp_path, capsys, other):
    with pytest.raises(SystemExit) as e:
        main(["-q", other])
    assert e.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_verbose_output_repeatable_with_seed(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    run_verbose(tmp_path, seed="4")
    first = capsys.readouterr().out
    run_verbose(tmp_path, seed="4")
    assert capsys.readouterr().out == first


def test_verbose_warning_stays_on_stderr_and_summary_is_last(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    (tmp_path / "in/broken.png").write_bytes(b"junk")
    run_verbose(tmp_path)

    captured = capsys.readouterr()
    assert "broken.png" not in captured.out
    assert "warning: skipped" in captured.err and "broken.png" in captured.err
    assert captured.out.splitlines()[-1] == "2 images processed, 1 skipped."


def test_verbose_without_preset_does_nothing(capsys):
    assert main(["--verbose"]) == 0
    assert "nothing to do" in capsys.readouterr().out.lower()


def test_format_report_uses_paths_as_given():
    report = FileReport(Path("x/a.png"), Path("x/b.png"), {"size": "4x4 (unchanged)", "saturation": "+1.0%"})
    assert format_report(report, Path("input"), Path("output")) == (
        f"{Path('input/x/a.png')} -> {Path('output/x/b.png')} | size 4x4 (unchanged) | saturation +1.0%"
    )


def test_short_option_v_is_the_same_as_verbose(make_image, tmp_path, capsys):
    preset = setup(make_image, tmp_path)
    args = ["--preset", str(preset), "--input", str(tmp_path / "in"),
            "--output", str(tmp_path / "out"), "--seed", "2"]
    main(args + ["--verbose"])
    long_form = capsys.readouterr().out
    main(args + ["-v"])
    assert capsys.readouterr().out == long_form
    assert long_form.count(" | size ") == 2


def run_cli(tmp_path, *extra, seed="1"):
    return main(["--preset", str(tmp_path / "preset.toml"), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out"), "--seed", seed, *extra])


@pytest.mark.parametrize("flag", ["--dry-run", "-n"])
def test_dry_run_prints_files_summary_and_writes_nothing(make_image, tmp_path, capsys, flag):
    setup(make_image, tmp_path)
    assert run_cli(tmp_path, flag) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Dry run (no changes will be made):"
    assert len(lines) == 5 and " | size 40x20 -> 10x5 | saturation " in lines[1]
    assert lines[-2:] == ["2 images would be processed, 0 skipped.", "Nothing was written."]
    assert not (tmp_path / "out").exists()


def test_dry_run_lines_equal_a_real_verbose_run(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    run_cli(tmp_path, "-n", seed="5")
    dry = capsys.readouterr().out.splitlines()[1:-2]  # without header and summary
    run_cli(tmp_path, "-v", seed="5")
    real = capsys.readouterr().out.splitlines()[:-1]  # without summary
    assert dry == real and len(dry) == 2
    assert (tmp_path / "out/a.png").exists()


def test_dry_run_with_verbose_prints_each_file_once(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    run_cli(tmp_path, "-n", "-v")
    assert len(capsys.readouterr().out.splitlines()) == 5


def test_dry_run_reports_bad_file_as_warning(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    (tmp_path / "in/broken.png").write_bytes(b"junk")
    assert run_cli(tmp_path, "-n") == 0

    captured = capsys.readouterr()
    assert "warning: skipped" in captured.err and "broken.png" in captured.err
    assert captured.out.splitlines()[-2:] == ["2 images would be processed, 1 skipped.", "Nothing was written."]


def test_dry_run_still_rejects_a_bad_preset(tmp_path, capsys):
    (tmp_path / "preset.toml").write_text('[[steps]]\nname = "nope"\n')
    (tmp_path / "in").mkdir()
    assert run_cli(tmp_path, "-n") == 2
    assert "error: unknown step 'nope'" in capsys.readouterr().err


def test_dry_run_without_preset_does_nothing(capsys):
    assert main(["-n"]) == 0
    assert "nothing to do" in capsys.readouterr().out.lower()


def test_singular_image_in_summary(make_image, tmp_path, capsys):
    preset = tmp_path / "preset.toml"
    preset.write_text(PRESET)
    make_image("in/a.png")
    run_cli(tmp_path)
    assert capsys.readouterr().out.splitlines()[-1] == "1 image processed, 0 skipped."
    run_cli(tmp_path, "-n")
    assert capsys.readouterr().out.splitlines()[-2:] == ["1 image would be processed, 0 skipped.", "Nothing was written."]


def test_no_images_found_summary(tmp_path, capsys):
    (tmp_path / "preset.toml").write_text(PRESET)
    (tmp_path / "in").mkdir()
    run_cli(tmp_path)
    assert capsys.readouterr().out.splitlines() == ["0 images processed, 0 skipped."]


def test_dry_run_header_not_printed_for_preset_errors(tmp_path, capsys):
    (tmp_path / "preset.toml").write_text('[[steps]]\nname = "nope"\n')
    (tmp_path / "in").mkdir()
    run_cli(tmp_path, "-n")
    assert "Dry run" not in capsys.readouterr().out


def test_real_run_has_no_dry_run_header_or_footer(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    run_cli(tmp_path, "-v")
    out = capsys.readouterr().out
    assert "Dry run" not in out and "Nothing was written" not in out


# ---------- EXIF orientation ----------

def write_preset(tmp_path, after=""):
    """Write the standard preset, followed by extra TOML (e.g. an [options] section)."""
    (tmp_path / "preset.toml").write_text(PRESET + after)


def test_verbose_line_shows_the_applied_orientation(make_tagged_image, tmp_path, capsys):
    make_tagged_image("in/phone.jpg", 6, size=(40, 20))
    write_preset(tmp_path)
    assert run_cli(tmp_path, "-v") == 0

    line = capsys.readouterr().out.splitlines()[0]
    assert re.search(r"\| size 20x40 -> 5x10 \| orientation EXIF \(rotated 90° cw\) \| saturation [+-]\d+\.\d%$", line)


def test_dry_run_prints_the_same_orientation_line(make_tagged_image, tmp_path, capsys):
    make_tagged_image("in/phone.jpg", 6, size=(40, 20))
    write_preset(tmp_path)
    run_cli(tmp_path, "-n", seed="3")
    dry = capsys.readouterr().out.splitlines()[1]
    run_cli(tmp_path, "-v", seed="3")
    real = capsys.readouterr().out.splitlines()[0]
    assert dry == real and "orientation EXIF (rotated 90° cw)" in dry


def test_exif_orientation_keep_in_the_preset(make_tagged_image, tmp_path, capsys):
    make_tagged_image("in/phone.jpg", 6, size=(40, 20))
    write_preset(tmp_path, "\n[options]\nexif_orientation = \"keep\"\n")
    run_cli(tmp_path, "-v")

    line = capsys.readouterr().out.splitlines()[0]
    assert "size 40x20 -> 10x5" in line and "| orientation" not in line
    with Image.open(tmp_path / "out/phone.jpg") as out:
        assert out.size == (10, 5)


def test_unknown_exif_orientation_is_a_preset_error(tmp_path, capsys):
    write_preset(tmp_path, '\n[options]\nexif_orientation = "no"\n')
    (tmp_path / "in").mkdir()
    assert run_cli(tmp_path) == 2
    assert "unknown exif_orientation 'no'" in capsys.readouterr().err


def test_top_level_exif_orientation_is_rejected_with_a_hint(tmp_path, capsys):
    (tmp_path / "preset.toml").write_text('exif_orientation = "keep"\n' + PRESET)
    (tmp_path / "in").mkdir()
    assert run_cli(tmp_path) == 2
    assert "option 'exif_orientation' belongs in the [options] section" in capsys.readouterr().err


# ---------- trim_borders ----------

TRIM_PRESET = """
[[steps]]
name = "trim_borders"

[[steps]]
name = "resize"
size = 10
"""


def test_verbose_and_dry_run_show_the_trim_entry(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    image = Image.new("RGB", (100, 60), (255, 255, 255))
    image.paste((200, 30, 30), (12, 8, 72, 28))
    image.save(tmp_path / "in/framed.png")
    (tmp_path / "preset.toml").write_text(TRIM_PRESET)

    run_cli(tmp_path, "-v")
    real = capsys.readouterr().out.splitlines()[0]
    run_cli(tmp_path, "-n")
    dry = capsys.readouterr().out.splitlines()[1]

    assert real.endswith("| size 100x60 -> 10x3 | trim L12 T8 R28 B32")
    assert dry == real


# ---------- auto_brightness ----------

def test_verbose_and_dry_run_show_the_brightness_entry(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    image = Image.new("L", (40, 30), 80)
    image.paste(140, (20, 0, 40, 30))
    image.save(tmp_path / "in/dark.png")
    (tmp_path / "preset.toml").write_text(
        '[[steps]]\nname = "auto_brightness"\ncutoff = 0\n\n[[steps]]\nname = "resize"\nsize = 20\n'
    )

    run_cli(tmp_path, "-v")
    real = capsys.readouterr().out.splitlines()[0]
    run_cli(tmp_path, "-n")
    dry = capsys.readouterr().out.splitlines()[1]

    assert real.endswith("| size 40x30 -> 20x15 | brightness levels 80-140 -> 0-255")
    assert dry == real


# ---------- [output] ----------

def write_output_preset(tmp_path, section=""):
    (tmp_path / "preset.toml").write_text(PRESET + section)


def test_conversion_end_to_end(make_image, tmp_path, capsys):
    make_image("in/a.png", size=(40, 20))
    make_image("in/sub/b.jpg", size=(20, 40))
    write_output_preset(tmp_path, '\n[output]\nformat = "webp"\nquality = 70\n')
    assert run_cli(tmp_path, "-v") == 0

    lines = capsys.readouterr().out.splitlines()
    assert f"{tmp_path / 'out/a.webp'} | size 40x20 -> 10x5 | saturation " in lines[0]
    assert f"{tmp_path / 'out/sub/b.webp'}" in lines[1]
    assert lines[-1] == "2 images processed, 0 skipped."
    with Image.open(tmp_path / "out/a.webp") as image:
        assert image.format == "WEBP" and image.size == (10, 5)


def test_name_clash_is_reported_without_verbose(make_image, tmp_path, capsys):
    make_image("in/a.png")
    make_image("in/a.jpg")
    write_output_preset(tmp_path, '\n[output]\nformat = "webp"\n')
    assert run_cli(tmp_path) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == [f"{tmp_path / 'in/a.jpg'} -> {tmp_path / 'out/a.webp'}",
                         f"{tmp_path / 'in/a.png'} -> {tmp_path / 'out/a-1.webp'}"]
    assert lines[2:] == [
        "2 images processed, 0 skipped.",
        "1 file got a number added to its name because the name was already taken:",
        f"  {tmp_path / 'in/a.png'} -> {tmp_path / 'out/a-1.webp'}",
    ]


def test_several_clashes_use_the_plural(make_image, tmp_path, capsys):
    for name in ("a.png", "a.jpg", "a.gif"):
        make_image(f"in/{name}")
    write_output_preset(tmp_path, '\n[output]\nformat = "webp"\n')
    run_cli(tmp_path)
    lines = capsys.readouterr().out.splitlines()
    assert lines[4] == "2 files got a number added to their names because the name was already taken:"
    assert len(lines) == 7


def test_clashes_are_reported_even_when_quiet(make_image, tmp_path, capsys):
    make_image("in/a.png")
    make_image("in/a.jpg")
    write_output_preset(tmp_path, '\n[output]\nformat = "webp"\n')
    run_cli(tmp_path, "-q")
    assert capsys.readouterr().out.splitlines() == [
        "1 file got a number added to its name because the name was already taken:",
        f"  {tmp_path / 'in/a.png'} -> {tmp_path / 'out/a-1.webp'}",
    ]


def test_dry_run_reports_clashes_too(make_image, tmp_path, capsys):
    make_image("in/a.png")
    make_image("in/a.jpg")
    write_output_preset(tmp_path, '\n[output]\nformat = "webp"\n')
    run_cli(tmp_path, "-n")

    lines = capsys.readouterr().out.splitlines()
    assert lines[-4:] == [
        "2 images would be processed, 0 skipped.",
        "1 file would get a number added to its name because the name was already taken:",
        f"  {tmp_path / 'in/a.png'} -> {tmp_path / 'out/a-1.webp'}",
        "Nothing was written.",
    ]
    assert not (tmp_path / "out").exists()


def test_verbose_line_shows_the_final_name(make_image, tmp_path, capsys):
    make_image("in/a.png")
    make_image("in/a.jpg")
    write_output_preset(tmp_path, '\n[output]\nformat = "webp"\n')
    run_cli(tmp_path, "-v")
    out = capsys.readouterr().out
    assert f"{tmp_path / 'in/a.png'} -> {tmp_path / 'out/a-1.webp'}" in out.splitlines()[1]


def test_no_clash_block_when_nothing_was_renamed(make_image, tmp_path, capsys):
    make_image("in/a.png")
    make_image("in/b.jpg")
    write_output_preset(tmp_path, '\n[output]\nformat = "webp"\n')
    run_cli(tmp_path)
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "2 images processed, 0 skipped." and len(lines) == 3


def test_keep_mode_has_no_clashes_and_keeps_names(make_image, tmp_path, capsys):
    make_image("in/a.png")
    make_image("in/a.jpg")
    write_output_preset(tmp_path)
    run_cli(tmp_path)
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "2 images processed, 0 skipped." and len(lines) == 3
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a.jpg", "a.png"]


def test_invalid_output_section_exits_with_an_error(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    write_output_preset(tmp_path, '\n[output]\nformat = "heic"\n')
    assert run_cli(tmp_path) == 2
    assert "[output]: unknown format 'heic'" in capsys.readouterr().err


# ---------- rotation ----------

def test_verbose_and_dry_run_show_the_rotation_entry(make_image, tmp_path, capsys):
    make_image("in/a.png", size=(100, 60))
    (tmp_path / "preset.toml").write_text(
        '[[steps]]\nname = "rnd_rotate"\n\n[[steps]]\nname = "resize"\nsize = 30\n'
    )
    run_cli(tmp_path, "-v", seed="3")
    real = capsys.readouterr().out.splitlines()[0]
    run_cli(tmp_path, "-n", seed="3")
    dry = capsys.readouterr().out.splitlines()[1]

    assert re.search(r"\| size 100x60 -> \d+x\d+ \| rotation [+-][0-5]\.\d°$", real)
    assert dry == real


def run_without_steps(make_image, tmp_path, preset_text, capsys, name="in/a.jpg"):
    make_image(name, size=(40, 20))
    preset = tmp_path / "preset.toml"
    preset.write_text(preset_text)
    code = main(["--preset", str(preset), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out")])
    return code, capsys.readouterr()


def test_format_alone_converts_without_steps(make_image, tmp_path, capsys):
    code, captured = run_without_steps(make_image, tmp_path, '[output]\nformat = "png"\n', capsys)
    assert code == 0 and "1 image processed" in captured.out
    with Image.open(tmp_path / "out/a.png") as image:
        assert (image.format, image.size) == ("PNG", (40, 20))


def test_keep_metadata_false_alone_strips_the_metadata(make_tagged_image, tmp_path, capsys):
    make_tagged_image("in/a.jpg", 1)
    preset = tmp_path / "preset.toml"
    preset.write_text("[output]\nkeep_metadata = false\n")
    code = main(["--preset", str(preset), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out")])
    assert code == 0
    with Image.open(tmp_path / "out/a.jpg") as image:
        assert not image.getexif()


def test_background_alone_is_rejected_without_steps(make_image, tmp_path, capsys):
    code, captured = run_without_steps(make_image, tmp_path, '[output]\nbackground = "red"\n', capsys)
    assert code == 2
    assert "define at least one [[steps]] entry" in captured.err


def test_short_options_i_and_o_are_the_same_as_input_and_output(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    assert main(["--preset", str(tmp_path / "preset.toml"), "-i", str(tmp_path / "in"),
                 "-o", str(tmp_path / "short"), "--seed", "1", "-q"]) == 0
    assert run_cli(tmp_path, "-q") == 0
    assert (tmp_path / "short/a.png").read_bytes() == (tmp_path / "out/a.png").read_bytes()
    assert (tmp_path / "short/sub/b.jpg").exists()
