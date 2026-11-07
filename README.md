# image-pipeline

Batch image transformation tool. Reads images from an input folder, applies a configurable, ordered pipeline of transformations, and writes the results to an output folder. Originals are never modified.

Python package: `imgpipe`. The pipeline preset is a TOML file. Dependency management: uv.

**Status.** Available steps: `trim_borders`, `rotate`, `rnd_rotate`, `resize`, `auto_brightness`, `rnd_saturation`. Photos with an EXIF orientation tag are made upright first (`exif_orientation`: `"apply"` by default, or `"keep"` / `"remove"`). Output (`[output]` section): keep the original format or convert to png, jpg, webp, avif, gif, tiff or bmp, with quality, a background for flattened transparency, and metadata stripping (on by default). Result files can be renamed from a pattern (`[rename]` section): original name, date and time, counter, random digits and letters, UUID.

## Quick start

The simplest run needs no options:

1. Put `preset.toml` (the example in this repository; releases include it) in a folder, and your images in an `input` folder next to it.
2. Run `./imgpipe` (Windows: `imgpipe.exe`) from that folder.
3. The results appear in the `output` folder. Your originals are never modified.

```bash
./imgpipe
```

`preset.toml` says what is done to the images (resize, rotate, convert, rename, ...). Edit it, or see `docs/en/preset.md`. The folders and the seed for random values can be set in the preset too, or with the options below.

## Standalone application

Standalone executables and `preset.toml` are available for Linux and Windows in the project's releases. They need no Python and take the same command line options as the Python package.

## Python package

```bash
uv sync
uv run pytest
uv run python -m imgpipe --seed 1
```

## Command line

```bash
uv run python -m imgpipe [--preset FILE] [-i DIR] [-o DIR] [--seed N] [--verbose | --quiet] [--dry-run]
```

| Option | Default | Meaning |
|---|---|---|
| `--preset FILE` | `preset.toml` | TOML pipeline preset. The default is read from the current folder; if it is missing the tool stops with an error. |
| `-i DIR`, `--input DIR` | `input_folder` of the preset, else `input` | Folder searched recursively for images. |
| `-o DIR`, `--output DIR` | `output_folder` of the preset, else `output` | Folder for the results; subfolders are mirrored. Must differ from the input folder. |
| `--seed N` | `seed` of the preset, else random | Makes random values repeatable. |
| `-v`, `--verbose` | off | Add the applied changes (size, saturation, ...) to the progress line of each file. |
| `-q`, `--quiet` | off | Print no progress lines and no summary. Warnings and errors are still shown. Not combinable with `-v` or `-n`. |
| `-n`, `--dry-run` | off | Show what would be done, in the same per-file format as `--verbose`, without writing any files. |
| `-h`, `--help` | | Show help. |


## Examples

Use another preset file instead of `preset.toml`:
```bash
./imgpipe --preset portraits.toml
```

Specify custom input and output folders:
```bash
./imgpipe -i photos -o processed
```

Preview the planned changes without modifying or creating output files:
```bash
./imgpipe --dry-run
```

By default one line per file (original path -> new path) shows the progress. To see the applied changes too:
```bash
./imgpipe --verbose
```

Run without any progress output:
```bash
./imgpipe --quiet
```

Use a fixed seed to make random transformations repeatable:
```bash
./imgpipe --seed 42
```

See `docs/en/preset.md` for all options and `AGENTS.md` for the layout and conventions.

To build the project, see `docs/en/building.md`.
