import io
import random
from pathlib import Path

import pytest
from PIL import Image, ImageCms, PngImagePlugin

from imgpipe import imageio, output
from imgpipe.config import load_config
from imgpipe.errors import ConfigError
from imgpipe.output import FORMATS, OutputSettings
from imgpipe.pipeline import Pipeline
from imgpipe.steps import create_step

ALL_FORMATS = list(FORMATS)
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def photo(size=(24, 16), mode="RGB", seed=1):
    rng = random.Random(seed)
    bands = len(mode)
    image = Image.new(mode, size)
    image.putdata([
        tuple(rng.randint(0, 255) for _ in range(bands)) if bands > 1 else rng.randint(0, 255)
        for _ in range(size[0] * size[1])
    ])
    return image


def write(image, path, source_format="PNG", metadata=None, orientation_applied=False, **settings):
    output.write(
        image, path, OutputSettings(**settings), source_format,
        metadata or imageio.Metadata(), orientation_applied,
    )
    return path


def reopen(path):
    with Image.open(path) as image:
        image.load()
        return image.copy(), image.format, dict(image.info), image.getexif()


# ---------- settings ----------

def test_defaults():
    s = OutputSettings()
    assert (s.format, s.quality, s.background, s.keep_metadata) == ("keep", None, "white", False)


@pytest.mark.parametrize("alias, name", [("jpeg", "jpg"), ("tif", "tiff"), ("jpg", "jpg"), ("keep", "keep")])
def test_format_aliases(alias, name):
    assert OutputSettings(format=alias).format == name


def test_unknown_format_lists_the_supported_ones():
    with pytest.raises(ValueError, match="unknown format 'heic'; known formats: keep, png, jpg, webp, avif, gif, tiff, bmp"):
        OutputSettings(format="heic")


@pytest.mark.parametrize("quality", [0, 101, -5])
def test_quality_range(quality):
    with pytest.raises(ValueError, match="'quality' must be between 1 and 100"):
        OutputSettings(quality=quality)


@pytest.mark.parametrize("fmt", ["png", "gif", "tiff", "bmp"])
def test_quality_rejected_for_formats_without_it(fmt):
    with pytest.raises(ValueError, match=f"option 'quality' is not used by format '{fmt}'"):
        OutputSettings(format=fmt, quality=80)


@pytest.mark.parametrize("fmt", ["keep", "jpg", "jpeg", "webp", "avif"])
def test_quality_accepted_where_it_is_used(fmt):
    assert OutputSettings(format=fmt, quality=80).quality == 80


@pytest.mark.parametrize("value", ["transparent", "#ff000080", "nope", "#12"])
def test_background_must_be_an_opaque_valid_color(value):
    with pytest.raises(ValueError, match="background"):
        OutputSettings(background=value)


@pytest.mark.parametrize("value", ["white", "#ff0000", "black"])
def test_valid_backgrounds(value):
    assert OutputSettings(background=value)


# ---------- names ----------

@pytest.mark.parametrize("fmt, suffix", [("png", ".png"), ("jpg", ".jpg"), ("webp", ".webp"), ("avif", ".avif"),
                                          ("gif", ".gif"), ("tiff", ".tiff"), ("bmp", ".bmp")])
def test_converting_replaces_the_suffix(fmt, suffix):
    target = OutputSettings(format=fmt).target_path(Path("sub/a.b.PNG"), "PNG")
    assert target == Path("sub") / f"a.b{suffix}"


@pytest.mark.parametrize("name", ["a.JPG", "a.jpeg", "a.jpe", "b.tif", "c.PNG"])
def test_keep_retains_the_original_spelling(name):
    assert OutputSettings().target_path(Path("x") / name, "JPEG") == Path("x") / name


# ---------- formats ----------

@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_every_format_round_trips(tmp_path, fmt):
    path = write(photo(), tmp_path / f"x.{fmt}", format=fmt)
    image, pillow_format, _, _ = reopen(path)
    assert pillow_format == FORMATS[fmt].pillow and image.size == (24, 16)


@pytest.mark.parametrize("fmt", ["png", "tiff", "bmp"])
def test_lossless_formats_keep_the_pixels(tmp_path, fmt):
    source = photo()
    image, _, _, _ = reopen(write(source, tmp_path / f"x.{fmt}", format=fmt))
    assert image.convert("RGB").tobytes() == source.tobytes()


@pytest.mark.parametrize(
    "source_format, fmt", [("JPEG", "jpg"), ("MPO", "jpg"), ("PNG", "png"), ("WEBP", "webp"), ("GIF", "gif"),
                           ("TIFF", "tiff"), ("BMP", "bmp"), ("AVIF", "avif")],
)
def test_keep_writes_the_source_format(tmp_path, source_format, fmt):
    path = write(photo(), tmp_path / "x.out", source_format=source_format)
    assert reopen(path)[1] == FORMATS[fmt].pillow


def test_keep_saves_other_formats_as_they_are(tmp_path):
    path = write(photo(), tmp_path / "x.tga", source_format="TGA")
    assert reopen(path)[1] == "TGA"


def test_parent_folders_are_created(tmp_path):
    path = write(photo(), tmp_path / "a" / "b" / "x.png", format="png")
    assert path.exists()


# ---------- flattening transparency ----------

def transparent_square(alpha=0):
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    image.paste((200, 30, 30, 255), (5, 0, 10, 10))
    image.paste((0, 0, 255, alpha), (0, 5, 5, 10))
    return image


@pytest.mark.parametrize("fmt", ["jpg", "gif", "bmp"])
def test_formats_without_alpha_flatten_onto_white_by_default(tmp_path, fmt):
    image, _, _, _ = reopen(write(transparent_square(), tmp_path / f"x.{fmt}", format=fmt))
    r, g, b = image.convert("RGB").getpixel((1, 1))  # a fully transparent area
    assert min(r, g, b) >= 250


def test_background_color_is_used(tmp_path):
    image, _, _, _ = reopen(write(transparent_square(), tmp_path / "x.bmp", format="bmp", background="#ff0000"))
    assert image.convert("RGB").getpixel((1, 1)) == (255, 0, 0)
    assert image.convert("RGB").getpixel((8, 5)) == (200, 30, 30)  # opaque content unchanged


def test_semi_transparent_pixels_blend_with_the_background(tmp_path):
    source = Image.new("RGBA", (4, 4), (0, 0, 0, 128))
    image, _, _, _ = reopen(write(source, tmp_path / "x.bmp", format="bmp", background="white"))
    value = image.convert("RGB").getpixel((0, 0))
    assert all(126 <= channel <= 128 for channel in value)  # half black over white


def test_gray_with_alpha_is_flattened_to_rgb(tmp_path):
    source = Image.new("LA", (4, 4), (0, 0))
    image, _, _, _ = reopen(write(source, tmp_path / "x.jpg", format="jpg", background="#00ff00"))
    assert image.mode == "RGB" and image.getpixel((1, 1))[1] > 200


@pytest.mark.parametrize("fmt", ["png", "tiff"])
def test_formats_with_alpha_keep_it_exactly(tmp_path, fmt):
    image, _, _, _ = reopen(write(transparent_square(alpha=77), tmp_path / f"x.{fmt}", format=fmt))
    assert image.mode == "RGBA"
    assert image.getpixel((1, 1))[3] == 0 and image.getpixel((8, 5))[3] == 255 and image.getpixel((1, 8))[3] == 77


@pytest.mark.parametrize("fmt", ["webp", "avif"])
def test_lossy_formats_with_alpha_keep_transparency(tmp_path, fmt):
    image, _, _, _ = reopen(write(transparent_square(), tmp_path / f"x.{fmt}", format=fmt, quality=100))
    assert image.mode == "RGBA" and image.getpixel((1, 1))[3] < 10 and image.getpixel((8, 5))[3] > 245


def test_palette_image_with_transparency_keeps_it_in_png(tmp_path):
    palette = Image.new("P", (6, 6), 0)
    palette.putpalette([0, 0, 0, 255, 0, 0])
    palette.paste(1, (0, 0, 3, 6))
    palette.info["transparency"] = 0  # palette index 0 is transparent
    image, _, _, _ = reopen(write(palette, tmp_path / "x.png", format="png"))
    rgba = image.convert("RGBA")
    assert rgba.getpixel((5, 5))[3] == 0 and rgba.getpixel((0, 0)) == (255, 0, 0, 255)


@pytest.mark.parametrize("fmt", ["webp", "avif"])
def test_gray_images_are_accepted_by_rgb_only_formats(tmp_path, fmt):
    for mode in ("L", "LA"):
        assert write(photo(mode=mode), tmp_path / f"{mode}.{fmt}", format=fmt).exists()


# ---------- quality ----------

def encoded(image, fmt, **options):
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **options)
    return buffer.getvalue()


def test_default_quality_is_90(tmp_path):
    source = photo((64, 64))
    written = write(source, tmp_path / "x.jpg", format="jpg").read_bytes()
    assert written == encoded(source, "JPEG", quality=90)


@pytest.mark.parametrize("fmt, pillow", [("jpg", "JPEG"), ("webp", "WEBP")])
def test_quality_changes_the_file(tmp_path, fmt, pillow):
    source = photo((64, 64))
    low = write(source, tmp_path / f"low.{fmt}", format=fmt, quality=20).stat().st_size
    high = write(source, tmp_path / f"high.{fmt}", format=fmt, quality=95).stat().st_size
    assert high > low
    assert (tmp_path / f"low.{fmt}").read_bytes() == encoded(source, pillow, quality=20)


def test_avif_accepts_quality(tmp_path):
    source = photo((32, 32))
    low = write(source, tmp_path / "low.avif", format="avif", quality=10).stat().st_size
    high = write(source, tmp_path / "high.avif", format="avif", quality=95).stat().st_size
    assert high > low


def test_keep_mode_applies_quality_to_jpeg_only(tmp_path):
    source = photo((64, 64))
    jpeg = write(source, tmp_path / "x.jpg", source_format="JPEG", quality=30)
    assert jpeg.read_bytes() == encoded(source, "JPEG", quality=30)
    write(source, tmp_path / "x.png", source_format="PNG", quality=30)  # ignored for PNG, no error


# ---------- metadata ----------

def exif_with(orientation=6, make="Camera Co"):
    exif = Image.Exif()
    exif[0x010F] = make
    exif[0x0112] = orientation
    exif.get_ifd(0x8825)[1] = "N"  # GPS latitude reference
    return exif


def rich_jpeg(tmp_path, name="src.jpg", orientation=6):
    path = tmp_path / name
    photo((32, 24)).save(
        path, exif=exif_with(orientation), icc_profile=SRGB, comment=b"private note",
        xmp=b"<x:xmpmeta xmlns:x='adobe:ns:meta/'><secret/></x:xmpmeta>",
    )
    return path


def test_source_really_has_the_metadata(tmp_path):
    loaded = imageio.load(rich_jpeg(tmp_path))
    meta = loaded.metadata
    assert loaded.orientation == 6 and meta.exif and meta.xmp and meta.icc_profile and meta.comment


def test_metadata_is_stripped_by_default_but_the_icc_profile_stays(tmp_path):
    loaded = imageio.load(rich_jpeg(tmp_path))
    path = write(loaded.image, tmp_path / "out.jpg", source_format="JPEG", metadata=loaded.metadata)
    _, _, info, exif = reopen(path)
    assert len(exif) == 0
    assert "comment" not in info and "xmp" not in info
    assert info.get("icc_profile") == SRGB


def test_keep_metadata_carries_exif_xmp_comment_and_icc(tmp_path):
    loaded = imageio.load(rich_jpeg(tmp_path))
    path = write(loaded.image, tmp_path / "out.jpg", source_format="JPEG", metadata=loaded.metadata,
                 keep_metadata=True)
    _, _, info, exif = reopen(path)
    assert exif[0x010F] == "Camera Co" and exif.get_ifd(0x8825)[1] == "N"
    assert exif[0x0112] == 6  # pixels were not rotated, so the tag stays
    assert info["comment"] == b"private note" and b"<secret/>" in info["xmp"]
    assert info["icc_profile"] == SRGB


def test_orientation_tag_is_dropped_when_the_pixels_were_rotated(tmp_path):
    loaded = imageio.load(rich_jpeg(tmp_path))
    path = write(loaded.image, tmp_path / "out.jpg", source_format="JPEG", metadata=loaded.metadata,
                 keep_metadata=True, orientation_applied=True)
    _, _, _, exif = reopen(path)
    assert 0x0112 not in exif and exif[0x010F] == "Camera Co"


def test_source_file_is_not_modified(tmp_path):
    src = rich_jpeg(tmp_path)
    before = src.read_bytes()
    loaded = imageio.load(src)
    write(loaded.image, tmp_path / "out.jpg", source_format="JPEG", metadata=loaded.metadata, keep_metadata=True)
    assert src.read_bytes() == before


def test_png_text_chunks_are_dropped_and_icc_is_kept(tmp_path):
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Somebody")
    src = tmp_path / "src.png"
    photo().save(src, pnginfo=info, icc_profile=SRGB)
    loaded = imageio.load(src)
    assert loaded.image.info.get("Author") == "Somebody"
    path = write(loaded.image, tmp_path / "out.png", source_format="PNG", metadata=loaded.metadata)
    _, _, out_info, _ = reopen(path)
    assert "Author" not in out_info and out_info["icc_profile"] == SRGB


def test_png_exif_is_written_only_with_keep_metadata(tmp_path):
    meta = imageio.Metadata(exif=exif_with().tobytes())
    plain = write(photo(), tmp_path / "plain.png", metadata=meta, format="png")
    kept = write(photo(), tmp_path / "kept.png", metadata=meta, format="png", keep_metadata=True)
    assert len(reopen(plain)[3]) == 0
    assert reopen(kept)[3][0x010F] == "Camera Co"


@pytest.mark.parametrize("fmt", ["webp", "avif"])
def test_webp_and_avif_icc_and_exif(tmp_path, fmt):
    meta = imageio.Metadata(exif=exif_with().tobytes(), icc_profile=SRGB, xmp=b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    stripped = write(photo(), tmp_path / f"s.{fmt}", metadata=meta, format=fmt)
    kept = write(photo(), tmp_path / f"k.{fmt}", metadata=meta, format=fmt, keep_metadata=True)
    assert len(reopen(stripped)[3]) == 0 and reopen(stripped)[2].get("icc_profile") == SRGB
    assert reopen(kept)[3][0x010F] == "Camera Co"


@pytest.mark.parametrize("fmt", ["tiff", "bmp", "gif"])
def test_keep_metadata_is_harmless_for_formats_without_it(tmp_path, fmt):
    meta = imageio.Metadata(exif=exif_with().tobytes(), xmp=b"<xmp/>", icc_profile=SRGB, comment=b"c")
    assert write(photo(), tmp_path / f"x.{fmt}", metadata=meta, format=fmt, keep_metadata=True).exists()


def test_gif_comment_follows_keep_metadata(tmp_path):
    meta = imageio.Metadata(comment=b"hello")
    assert reopen(write(photo(), tmp_path / "a.gif", metadata=meta, format="gif"))[2].get("comment") is None
    assert reopen(write(photo(), tmp_path / "b.gif", metadata=meta, format="gif", keep_metadata=True))[2]["comment"] == b"hello"


def test_loading_damaged_exif_still_gives_the_image(tmp_path):
    path = tmp_path / "x.jpg"
    photo().save(path, exif=b"Exif\x00\x00garbage garbage garbage")
    loaded = imageio.load(path)
    assert loaded.image.size == (24, 16)


def test_a_stale_info_entry_does_not_leak(tmp_path):
    image = photo()
    image.info["comment"] = b"stale"
    image.info["transparency"] = (1, 2, 3)
    path = write(image, tmp_path / "x.jpg", format="jpg")
    assert "comment" not in reopen(path)[2]
    assert image.info["comment"] == b"stale"  # the caller's image is restored


# ---------- name clashes ----------

def build(settings=None, steps=None):
    return Pipeline([create_step(*s) for s in (steps or [("resize", {"size": 10})])], True, settings)


def make_files(tmp_path, names, size=(20, 10)):
    for name in names:
        path = tmp_path / "in" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        photo(size).save(path)


def run(pipeline, tmp_path, dry_run=False, out="out"):
    reports = []
    result = pipeline.run(tmp_path / "in", tmp_path / out, random.Random(1), reports.append, dry_run=dry_run)
    return result, reports


def test_clash_gets_a_number(tmp_path):
    make_files(tmp_path, ["a.png", "a.jpg"])
    result, reports = run(build(OutputSettings(format="webp")), tmp_path)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a-1.webp", "a.webp"]
    assert [(s.as_posix(), t.as_posix()) for s, t in result.renamed] == [("a.png", "a-1.webp")]
    assert [r.target.as_posix() for r in reports] == ["a.webp", "a-1.webp"]  # sorted input: a.jpg, a.png
    assert [r.source.as_posix() for r in reports] == ["a.jpg", "a.png"]


def test_three_way_clash(tmp_path):
    make_files(tmp_path, ["a.png", "a.jpg", "a.gif"])
    result, _ = run(build(OutputSettings(format="webp")), tmp_path)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a-1.webp", "a-2.webp", "a.webp"]
    assert len(result.renamed) == 2


def test_generated_name_skips_names_that_are_taken(tmp_path):
    make_files(tmp_path, ["a-1.png", "a.jpg", "a.png"])  # sorted: a-1.png, a.jpg, a.png
    result, _ = run(build(OutputSettings(format="webp")), tmp_path)
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a-1.webp", "a-2.webp", "a.webp"]
    assert [(s.as_posix(), t.as_posix()) for s, t in result.renamed] == [("a.png", "a-2.webp")]


def test_different_folders_do_not_clash(tmp_path):
    make_files(tmp_path, ["a.png", "sub/a.jpg", "other/a.gif"])
    result, _ = run(build(OutputSettings(format="webp")), tmp_path)
    assert not result.renamed
    assert (tmp_path / "out/a.webp").exists() and (tmp_path / "out/sub/a.webp").exists()


def test_keep_mode_never_renames(tmp_path):
    make_files(tmp_path, ["a.png", "a.jpg"])
    result, _ = run(build(), tmp_path)
    assert not result.renamed
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a.jpg", "a.png"]


def test_dry_run_gives_the_same_names_and_writes_nothing(tmp_path):
    make_files(tmp_path, ["a.png", "a.jpg", "b.png"])
    pipeline = build(OutputSettings(format="webp"))
    real_result, real = run(pipeline, tmp_path, out="real")
    dry_result, dry = run(pipeline, tmp_path, dry_run=True, out="dry")
    assert dry == real and dry_result.renamed == real_result.renamed
    assert not (tmp_path / "dry").exists()


def test_a_skipped_file_does_not_reserve_its_name(tmp_path):
    make_files(tmp_path, ["b.png"])
    (tmp_path / "in/a.png").write_bytes(b"junk")  # sorted first, fails to load
    make_files(tmp_path, ["a.jpg"])
    result, _ = run(build(OutputSettings(format="webp")), tmp_path)
    assert not result.renamed and (tmp_path / "out/a.webp").exists()


# ---------- in the pipeline: converted files ----------

def test_pipeline_converts_and_applies_quality_and_background(tmp_path):
    make_files(tmp_path, ["a.png"])
    transparent = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    transparent.paste((10, 200, 10, 255), (0, 0, 10, 10))
    transparent.save(tmp_path / "in/t.png")
    pipeline = build(OutputSettings(format="jpg", quality=80, background="#ff0000"))
    result, _ = run(pipeline, tmp_path)
    assert not result.skipped
    with Image.open(tmp_path / "out/t.jpg") as image:
        assert image.format == "JPEG" and image.size == (10, 5)
        r, g, b = image.getpixel((8, 2))
        assert r > 200 and g < 60  # flattened onto red


def test_exif_orientation_flows_to_the_output(tmp_path):
    src = tmp_path / "in/phone.jpg"
    src.parent.mkdir()
    photo((40, 20)).save(src, exif=exif_with(6))
    keep = build(OutputSettings(keep_metadata=True))
    run(keep, tmp_path)
    with Image.open(tmp_path / "out/phone.jpg") as image:
        assert image.size == (5, 10) and 0x0112 not in image.getexif()  # rotated: tag removed
        assert image.getexif()[0x010F] == "Camera Co"
    off = Pipeline([create_step("resize", {"size": 10})], False, OutputSettings(keep_metadata=True))
    off.run(tmp_path / "in", tmp_path / "out2", random.Random(1))
    with Image.open(tmp_path / "out2/phone.jpg") as image:
        assert image.size == (10, 5) and image.getexif()[0x0112] == 6  # not rotated: tag kept
