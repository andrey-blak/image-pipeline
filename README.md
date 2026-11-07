# image-pipeline

Batch image transformation tool. Reads images from an input folder, applies a configurable, ordered pipeline of transformations, and writes the results to an output folder. Originals are never modified.

Python package: `imgpipe`. Pipeline configuration is TOML. Dependency management: uv.

**Status: early.** Available steps: `resize`, `rnd_saturation`. Photos with an EXIF orientation tag are made upright first (`fix_orientation`, on by default). Output currently keeps the original names, formats and subfolders; renaming and format conversion are not implemented yet.

## Quick start

```
uv sync
uv run pytest
uv run python -m imgpipe --config config.example.toml --input input --output output --seed 1
```

## Command line

```
uv run python -m imgpipe [--config FILE] [--input DIR] [--output DIR] [--seed N] [--verbose] [--dry-run]
```

| Option | Default | Meaning |
|---|---|---|
| `--config FILE` | none | TOML pipeline config. Without it the tool does nothing. |
| `--input DIR` | `input` | Folder searched recursively for images. |
| `--output DIR` | `output` | Folder for the results; subfolders are mirrored. Must differ from the input folder. |
| `--seed N` | random | Makes random values repeatable. |
| `-v`, `--verbose` | off | Print one line per processed file: original path, new path, and the applied changes (size, saturation). |
| `-n`, `--dry-run` | off | Show what would be done, in the same per-file format as `--verbose`, without writing any files. |
| `-h`, `--help` | | Show help. |

Exit code: `0` on success (files that cannot be processed are skipped with a warning), `2` on a config or folder error.

See `docs/en/config.md` for all options and `AGENTS.md` for the layout and conventions.
