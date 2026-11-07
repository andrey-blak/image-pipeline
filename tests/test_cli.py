import re
from pathlib import Path

from PIL import Image

from imgpipe.cli import format_report, main
from imgpipe.pipeline import FileReport

CONFIG = """
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
    config = tmp_path / "config.toml"
    config.write_text(CONFIG)
    return config


def test_end_to_end(make_image, tmp_path, capsys):
    config = setup(make_image, tmp_path)
    code = main(["--config", str(config), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out"), "--seed", "1"])

    assert code == 0
    assert "Processed 2 image(s), skipped 0." in capsys.readouterr().out
    with Image.open(tmp_path / "out/a.png") as a, Image.open(tmp_path / "out/sub/b.jpg") as b:
        assert a.size == (10, 5)
        assert b.size == (5, 10)


def test_same_seed_twice_gives_identical_output(make_image, tmp_path):
    config = setup(make_image, tmp_path)
    for out in ("o1", "o2"):
        main(["--config", str(config), "--input", str(tmp_path / "in"),
              "--output", str(tmp_path / out), "--seed", "9"])
    for rel in ("a.png", "sub/b.jpg"):
        assert (tmp_path / "o1" / rel).read_bytes() == (tmp_path / "o2" / rel).read_bytes()


def test_no_config_does_nothing(make_image, tmp_path, capsys):
    make_image("in/a.png")
    code = main(["--input", str(tmp_path / "in"), "--output", str(tmp_path / "out")])

    assert code == 0
    assert "nothing to do" in capsys.readouterr().out.lower()
    assert not (tmp_path / "out").exists()


def test_bad_config_reports_error(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text('[[steps]]\nname = "nope"\n')
    code = main(["--config", str(config), "--input", str(tmp_path)])

    assert code == 2
    assert "error: unknown step 'nope'" in capsys.readouterr().err


def test_missing_input_folder(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG)
    code = main(["--config", str(config), "--input", str(tmp_path / "nope")])

    assert code == 2
    assert "input folder not found" in capsys.readouterr().err


def test_bad_file_gives_warning_and_exit_zero(make_image, tmp_path, capsys):
    config = setup(make_image, tmp_path)
    (tmp_path / "in/broken.png").write_bytes(b"junk")
    code = main(["--config", str(config), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out")])

    captured = capsys.readouterr()
    assert code == 0
    assert "warning: skipped" in captured.err and "broken.png" in captured.err
    assert "Processed 2 image(s), skipped 1." in captured.out


def run_verbose(tmp_path, seed="1"):
    return main(["--config", str(tmp_path / "config.toml"), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out"), "--seed", seed, "--verbose"])


def test_verbose_lists_each_file(make_image, tmp_path, capsys):
    setup(make_image, tmp_path)
    assert run_verbose(tmp_path) == 0

    lines = capsys.readouterr().out.splitlines()
    pattern = r"{src} -> {dst} \| size {old} -> {new} \| saturation [+-]\d+\.\d%"
    for line, (rel, old, new) in zip(lines, [("a.png", "40x20", "10x5"), ("sub/b.jpg", "20x40", "5x10")]):
        assert re.fullmatch(
            pattern.format(src=re.escape(f"{tmp_path}/in/{rel}"), dst=re.escape(f"{tmp_path}/out/{rel}"),
                           old=old, new=new),
            line,
        )
    assert lines[-1] == "Processed 2 image(s), skipped 0."
    assert len(lines) == 3


def test_no_file_lines_without_verbose(make_image, tmp_path, capsys):
    config = setup(make_image, tmp_path)
    main(["--config", str(config), "--input", str(tmp_path / "in"), "--output", str(tmp_path / "out")])
    assert capsys.readouterr().out.splitlines() == ["Processed 2 image(s), skipped 0."]


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
    assert captured.out.splitlines()[-1] == "Processed 2 image(s), skipped 1."


def test_verbose_without_config_does_nothing(capsys):
    assert main(["--verbose"]) == 0
    assert "nothing to do" in capsys.readouterr().out.lower()


def test_format_report_uses_paths_as_given():
    report = FileReport(Path("x/a.png"), Path("x/b.png"), {"size": "4x4 (unchanged)", "saturation": "+1.0%"})
    assert format_report(report, Path("input"), Path("output")) == (
        "input/x/a.png -> output/x/b.png | size 4x4 (unchanged) | saturation +1.0%"
    )


def test_short_option_v_is_the_same_as_verbose(make_image, tmp_path, capsys):
    config = setup(make_image, tmp_path)
    args = ["--config", str(config), "--input", str(tmp_path / "in"),
            "--output", str(tmp_path / "out"), "--seed", "2"]
    main(args + ["--verbose"])
    long_form = capsys.readouterr().out
    main(args + ["-v"])
    assert capsys.readouterr().out == long_form
    assert long_form.count(" | size ") == 2
