# Pipeline config

A TOML file passed with `--config`. It is separate from `pyproject.toml`. Without `--config` the tool does nothing.

The file holds an ordered list of steps (`[[steps]]` tables). Each step has a `name` and its own options. Steps run in the order written; every step receives the result of the previous one. Unknown step names, unknown or missing options, and values of the wrong type are rejected before any image is processed.

Only the `steps` key is accepted at the top level for now.

## Steps

Steps whose name starts with `rnd_` draw random values separately for each image; the values are repeatable with `--seed`. Other steps are deterministic.

### `resize`
Scales an image keeping its proportions.

| Option | Type | Default | Meaning |
|---|---|---|---|
| `size` | int | required | Target length in pixels (at least 1). |
| `mode` | string | `"longest_side"` | `longest_side`: the longer side becomes `size`. |
| `upscale` | bool | `false` | Also enlarge images whose longer side is smaller than `size`. |

### `rnd_saturation`
Changes saturation by a random percent in `[min_percent, max_percent]`, drawn separately for each image (repeatable with `--seed`). Transparency is preserved. Grayscale images are left unchanged.

| Option | Type | Default | Meaning |
|---|---|---|---|
| `min_percent` | float | required | Lower bound, e.g. `3` for +3%. Must be above -100. |
| `max_percent` | float | required | Upper bound; not less than `min_percent`. |

## Command line

```
uv run python -m imgpipe --config config.toml [--input input] [--output output] [--seed N]
```

- `--input` (default `input`): searched recursively for images.
- `--output` (default `output`): receives the results with the same relative paths, names and formats as the originals. This is temporary behavior until the output/naming section exists. The output folder must differ from the input folder; if it lies inside the input folder it is not rescanned.
- `--seed`: makes random values repeatable.
- Files that cannot be read or processed are skipped with a warning; the batch continues. Originals are never modified.
