import random
import re
from datetime import datetime
from pathlib import Path

import pytest

from imgpipe.cli import main
from imgpipe.config import load_config
from imgpipe.errors import ConfigError
from imgpipe.naming import Literal, RenameSettings, Token, parse_pattern
from imgpipe.output import OutputSettings
from imgpipe.pipeline import Pipeline
from imgpipe.steps import create_step

NOW = datetime(2023, 8, 5, 14, 3, 9, 874567)
SOURCE = Path("Holiday.JPG")


def render(pattern, source=SOURCE, counter=7, now=NOW, seed=1):
    return RenameSettings(pattern).name(source, counter, now, random.Random(seed))


# ---------- parser ----------

def test_runs_of_letters_become_tokens_and_the_rest_is_literal():
    assert parse_pattern("N-YYYY_dd.x 1") == [
        Token("N", 1), Literal("-"), Token("Y", 4), Literal("_"), Token("d", 2), Literal(".x 1"),
    ]


def test_unlisted_letters_are_literal():
    assert parse_pattern("xyz") == [Literal("xyz")]


def test_neighbouring_runs_of_different_letters():
    assert parse_pattern("RRaaAALLBB") == [
        Token("R", 2), Token("a", 2), Token("A", 2), Token("L", 2), Token("B", 2),
    ]


def test_quoted_text_is_literal_even_with_token_letters():
    assert parse_pattern("'IMG_'CCC") == [Literal("IMG_"), Token("C", 3)]
    assert render("'N'") == "N"


def test_unquoted_token_letters_are_tokens():
    # "IMG_" read without quotes: I, month, G_
    assert render("IMG_") == "I8G_"


@pytest.mark.parametrize("pattern, expected", [("x''y", "x'y"), ("'it''s'", "it's"), ("''", "'")])
def test_doubled_quote_is_one_quote(pattern, expected):
    assert render(pattern) == expected


def test_unclosed_quote():
    with pytest.raises(ValueError, match="quote at position 1 is never closed"):
        parse_pattern("'abc")


def test_empty_pattern():
    with pytest.raises(ValueError, match="'pattern' must not be empty"):
        parse_pattern("")


@pytest.mark.parametrize("pattern", [
    "YYY", "Y", "MMM", "ddd", "HHH", "hhh", "mmm", "sss", "SSSS", "NN", "EE", "UU",
])
def test_wrong_letter_counts_are_rejected(pattern):
    with pytest.raises(ValueError, match=f"'{pattern}' is not valid; '{pattern[0]}' must be repeated"):
        parse_pattern(pattern)


@pytest.mark.parametrize("pattern", ["a/b", "x\\y", "'a:b'", "x*", "x?", 'x"', "<x>", "x|y"])
def test_forbidden_file_name_characters(pattern):
    with pytest.raises(ValueError, match="cannot be used in a file name"):
        parse_pattern(pattern)


def test_wide_counts_for_counter_and_random_tokens():
    assert parse_pattern("CCCCCC") == [Token("C", 6)]
    assert parse_pattern("R" * 12) == [Token("R", 12)]


def test_counter_start_must_not_be_negative():
    with pytest.raises(ValueError, match="'counter_start' must not be negative"):
        RenameSettings("C", counter_start=-1)


# ---------- rendering ----------

@pytest.mark.parametrize("pattern, expected", [
    ("YYYY", "2023"), ("YY", "23"), ("M", "8"), ("MM", "08"), ("d", "5"), ("dd", "05"),
    ("H", "14"), ("HH", "14"), ("h", "2"), ("hh", "02"), ("m", "3"), ("mm", "03"),
    ("s", "9"), ("ss", "09"), ("S", "8"), ("SS", "87"), ("SSS", "874"),
    ("YYYY-MM-dd", "2023-08-05"), ("HHmmssSSS", "140309874"),
])
def test_date_and_time_tokens(pattern, expected):
    assert render(pattern) == expected


@pytest.mark.parametrize("hour, h, H", [(0, "12", "0"), (1, "1", "1"), (12, "12", "12"),
                                         (13, "1", "13"), (23, "11", "23")])
def test_clock_hour_and_hour_of_day(hour, h, H):
    now = NOW.replace(hour=hour)
    assert (render("h", now=now), render("H", now=now)) == (h, H)


def test_fraction_of_a_second_is_truncated_and_keeps_leading_zeros():
    now = NOW.replace(microsecond=5_000)
    assert (render("S", now=now), render("SS", now=now), render("SSS", now=now)) == ("0", "00", "005")


def test_year_is_padded():
    assert render("YYYY", now=NOW.replace(year=987)) == "0987"
    assert render("YY", now=NOW.replace(year=2005)) == "05"


@pytest.mark.parametrize("pattern, counter, expected", [
    ("C", 7, "7"), ("CC", 7, "07"), ("CCC", 7, "007"), ("C", 12, "12"), ("CC", 123, "123"), ("CCC", 0, "000"),
])
def test_counter_width(pattern, counter, expected):
    assert render(pattern, counter=counter) == expected


def test_name_and_extension_tokens():
    assert render("N") == "Holiday"
    assert render("N", Path("a.b.c.png")) == "a.b.c"
    assert render("E") == "JPG"
    assert render("N_E") == "Holiday_JPG"
    assert render("E", Path("noext")) == ""


def test_the_example_pattern():
    text = render("N-YYYY-MM-dd-HHmmssSSS-CCC-RRaaAALLBB")
    assert re.fullmatch(
        r"Holiday-2023-08-05-140309874-007-\d{2}[a-z]{2}[A-Z]{2}[A-Za-z]{2}[A-Za-z0-9]{2}", text
    )


# ---------- random tokens ----------

@pytest.mark.parametrize("letter, pattern", [
    ("R", r"[0-9]"), ("A", r"[A-Z]"), ("a", r"[a-z]"), ("L", r"[A-Za-z]"), ("B", r"[A-Za-z0-9]"),
])
def test_random_tokens_use_their_character_set(letter, pattern):
    for count in (1, 4, 30):
        assert re.fullmatch(f"{pattern}{{{count}}}", render(letter * count))


def test_random_tokens_cover_their_whole_set():
    text = render("L" * 2000)
    assert set(text) >= set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert set(render("R" * 500)) == set("0123456789")
    mixed = render("B" * 2000)
    assert any(c.isdigit() for c in mixed) and any(c.islower() for c in mixed)
    assert any(c.isupper() for c in mixed)


def test_random_text_repeats_with_the_seed_and_differs_between_seeds():
    assert render("RRRRRRRR", seed=5) == render("RRRRRRRR", seed=5)
    assert render("RRRRRRRR", seed=5) != render("RRRRRRRR", seed=6)


def test_uuid_is_version_4_and_repeats_with_the_seed():
    pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
    assert pattern.fullmatch(render("U"))
    assert render("U", seed=2) == render("U", seed=2)
    assert render("U", seed=2) != render("U", seed=3)


def test_tokens_without_randomness_do_not_draw_numbers():
    rng = random.Random(1)
    state = rng.getstate()
    RenameSettings("N-YYYY-CCC").name(SOURCE, 1, NOW, rng)
    assert rng.getstate() == state


# ---------- config ----------

def config(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text + '\n[[steps]]\nname = "resize"\nsize = 10\n')
    return path


def test_rename_table_is_loaded(tmp_path):
    rename = load_config(config(tmp_path, '[rename]\npattern = "N-CC"\ncounter_start = 5')).rename
    assert (rename.pattern, rename.counter_start) == ("N-CC", 5)


def test_rename_defaults_and_absent_table(tmp_path):
    assert load_config(config(tmp_path, '[rename]\npattern = "N"')).rename.counter_start == 1
    assert load_config(config(tmp_path, "")).rename is None


def test_rename_table_may_come_after_the_steps(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[[steps]]\nname = "resize"\nsize = 10\n\n[rename]\npattern = "N"\n')
    assert load_config(path).rename.pattern == "N"


def test_rename_needs_a_pattern(tmp_path):
    with pytest.raises(ConfigError, match=r"\[rename\] needs a 'pattern'"):
        load_config(config(tmp_path, "[rename]\ncounter_start = 2"))


def test_rename_unknown_option(tmp_path):
    with pytest.raises(ConfigError, match=r"unknown option\(s\) suffix in \[rename\]; known options: pattern, counter_start"):
        load_config(config(tmp_path, '[rename]\npattern = "N"\nsuffix = 1'))


@pytest.mark.parametrize("body, message", [
    ("pattern = 5", "option 'pattern' must be str"),
    ('pattern = "N"\ncounter_start = "1"', "option 'counter_start' must be int"),
    ('pattern = "N"\ncounter_start = true', "option 'counter_start' must be int"),
])
def test_rename_wrong_types(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load_config(config(tmp_path, f"[rename]\n{body}"))


def test_rename_value_errors_name_the_section(tmp_path):
    with pytest.raises(ConfigError, match=r"\[rename\]: 'pattern': 'YYY' is not valid"):
        load_config(config(tmp_path, '[rename]\npattern = "YYY"'))
    with pytest.raises(ConfigError, match=r"\[rename\]: 'counter_start' must not be negative"):
        load_config(config(tmp_path, '[rename]\npattern = "N"\ncounter_start = -1'))


def test_bare_top_level_pattern_gets_a_hint(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('pattern = "N"\n[[steps]]\nname = "resize"\nsize = 10\n')
    with pytest.raises(ConfigError, match=r"option 'pattern' belongs in the \[rename\] table"):
        load_config(path)


# ---------- pipeline ----------

def run(tmp_path, pattern, counter_start=1, dry_run=False, seed=1, out="out", output=None):
    reports = []
    pipe = Pipeline(
        [create_step("resize", {"size": 10})],
        output_settings=output,
        rename=RenameSettings(pattern, counter_start),
        clock=lambda: NOW,
    )
    rng = random.Random(seed)
    result = pipe.run(tmp_path / "in", tmp_path / out, rng, reports.append, dry_run=dry_run)
    return result, reports, rng


def test_extension_is_appended_in_its_original_spelling(make_image, tmp_path):
    make_image("in/a.JPG")
    make_image("in/b.png")
    _, reports, _ = run(tmp_path, "'x-'C")
    assert sorted(r.target.name for r in reports) == ["x-1.JPG", "x-2.png"]
    assert all((tmp_path / "out" / r.target).is_file() for r in reports)


def test_extension_follows_the_output_format(make_image, tmp_path):
    make_image("in/a.png")
    _, reports, _ = run(tmp_path, "N-YYYY", output=OutputSettings(format="webp"))
    assert reports[0].target == Path("a-2023.webp")


def test_original_extension_token_is_only_text(make_image, tmp_path):
    make_image("in/a.png")
    _, reports, _ = run(tmp_path, "N_E", output=OutputSettings(format="jpg"))
    assert reports[0].target == Path("a_png.jpg")


def test_subfolders_are_mirrored(make_image, tmp_path):
    make_image("in/sub/deep/a.png")
    _, reports, _ = run(tmp_path, "N-CC")
    assert reports[0].target == Path("sub/deep/a-01.png")
    assert (tmp_path / "out/sub/deep/a-01.png").is_file()


def test_counter_follows_processing_order_and_start(make_image, tmp_path):
    for name in ("a", "b", "c"):
        make_image(f"in/{name}.png")
    _, reports, _ = run(tmp_path, "'n'CC", counter_start=10)
    assert [(r.source.name, r.target.name) for r in reports] == [
        ("a.png", "n10.png"), ("b.png", "n11.png"), ("c.png", "n12.png"),
    ]


def test_skipped_files_do_not_use_a_counter_value(make_image, tmp_path):
    make_image("in/a.png")
    make_image("in/c.png")
    (tmp_path / "in/b.png").write_bytes(b"not an image")
    result, reports, _ = run(tmp_path, "'n'C")
    assert len(result.skipped) == 1
    assert [r.target.name for r in reports] == ["n1.png", "n2.png"]


def test_a_taken_name_gets_a_number(make_image, tmp_path):
    make_image("in/a.png")
    make_image("in/b.png")
    result, reports, _ = run(tmp_path, "x_y")
    assert [r.target.name for r in reports] == ["x_y.png", "x_y-1.png"]
    assert result.renamed == [(Path("b.png"), Path("x_y-1.png"))]


def test_seeded_runs_give_the_same_names(make_image, tmp_path):
    make_image("in/a.png")
    make_image("in/b.png")
    first = [r.target for r in run(tmp_path, "RRRR_U", seed=3, out="o1")[1]]
    second = [r.target for r in run(tmp_path, "RRRR_U", seed=3, out="o2")[1]]
    other = [r.target for r in run(tmp_path, "RRRR_U", seed=4, out="o3")[1]]
    assert first == second != other


def test_without_rename_names_stay_the_same(make_image, tmp_path):
    make_image("in/a.png")
    reports = []
    Pipeline([create_step("resize", {"size": 10})]).run(
        tmp_path / "in", tmp_path / "out", random.Random(1), reports.append
    )
    assert reports[0].target == Path("a.png")


def test_dry_run_shows_the_real_names_and_writes_nothing(make_image, tmp_path):
    make_image("in/a.png")
    make_image("in/sub/b.jpg")
    pattern = "N-YYYYMMdd-CCC-RRRRaaaa-U"
    real_result, real, real_rng = run(tmp_path, pattern, out="real")
    dry_result, dry, dry_rng = run(tmp_path, pattern, dry_run=True, out="dry")

    assert [r.target for r in dry] == [r.target for r in real]
    assert [r.changes for r in dry] == [r.changes for r in real]
    assert dry_rng.getstate() == real_rng.getstate()
    assert len(dry_result.processed) == len(real_result.processed) == 2
    assert not (tmp_path / "dry").exists()


# ---------- command line ----------

def test_cli_verbose_shows_the_new_names(make_image, tmp_path, capsys):
    make_image("in/a.png")
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[rename]\npattern = "\'photo-\'CCC"\n\n[[steps]]\nname = "resize"\nsize = 10\n'
    )
    code = main(["--config", str(config_path), "--input", str(tmp_path / "in"),
                 "--output", str(tmp_path / "out"), "-v"])

    assert code == 0
    assert f"{tmp_path / 'in/a.png'} -> {tmp_path / 'out/photo-001.png'} |" in capsys.readouterr().out
    assert (tmp_path / "out/photo-001.png").is_file()


def test_cli_reports_a_bad_pattern(make_image, tmp_path, capsys):
    make_image("in/a.png")
    config_path = tmp_path / "config.toml"
    config_path.write_text('[rename]\npattern = "YYY"\n\n[[steps]]\nname = "resize"\nsize = 10\n')
    code = main(["--config", str(config_path), "--input", str(tmp_path / "in")])

    assert code == 2
    assert "[rename]: 'pattern': 'YYY' is not valid" in capsys.readouterr().err
