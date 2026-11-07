# image-pipeline

Batch image transformation tool. Reads images from an input folder, applies a configurable, ordered pipeline of transformations, and writes the results to an output folder. Originals are never modified.

Python package: `imgpipe`. The pipeline preset is a TOML file. Dependency management: uv.

**Status.** Available steps: `trim_borders`, `rotate`, `rnd_rotate`, `resize`, `auto_brightness`, `rnd_saturation`. Photos with an EXIF orientation tag are made upright first (`exif_orientation`: `"apply"` by default, or `"keep"` / `"remove"`). Output (`[output]` section): keep the original format or convert to png, jpg, webp, avif, gif, tiff or bmp, with quality, a background for flattened transparency, and metadata stripping (on by default). Result files can be renamed from a pattern (`[rename]` section): original name, date and time, counter, random digits and letters, UUID.

## Python package quick start

```bash
uv sync
uv run pytest
uv run python -m imgpipe --preset preset.example.toml --input input --output output --seed 1
```

## Standalone application

A standalone executable is available for Linux and Windows in the project's releases.

Run the application from a terminal:

```bash
./imgpipe --preset preset.toml --input input --output output --seed 1
```

The executable uses the same command line options as the Python package.

Original images are never modified.

## Command line

```bash
uv run python -m imgpipe [--preset FILE] [--input DIR] [--output DIR] [--seed N] [--verbose] [--dry-run]
```

| Option | Default | Meaning |
|---|---|---|
| `--preset FILE` | none | TOML pipeline preset. Without it the tool does nothing. |
| `--input DIR` | `input` | Folder searched recursively for images. |
| `--output DIR` | `output` | Folder for the results; subfolders are mirrored. Must differ from the input folder. |
| `--seed N` | random | Makes random values repeatable. |
| `-v`, `--verbose` | off | Print one line per processed file: original path, new path, and the applied changes (size, saturation). |
| `-n`, `--dry-run` | off | Show what would be done, in the same per-file format as `--verbose`, without writing any files. |
| `-h`, `--help` | | Show help. |


## Examples

Process images using a preset file:
```bash
./imgpipe --preset preset.toml
```

Specify custom input and output folders:
```bash
./imgpipe --preset preset.toml --input photos --output processed
```

Preview the planned changes without modifying or creating output files:
```bash
./imgpipe --preset preset.toml --dry-run
```

Process images with verbose output:
```bash
./imgpipe --preset preset.toml --verbose
```

Use a fixed seed to make random transformations repeatable:
```bash
./imgpipe --preset preset.toml --seed 42
```

See `docs/en/preset.md` for all options and `AGENTS.md` for the layout and conventions.

To build the project, see `docs/en/building.md`.
