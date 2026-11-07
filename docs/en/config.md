# Pipeline config

A TOML file passed with `--config`. It is separate from `pyproject.toml`. Without `--config` the tool does nothing.

The file holds an ordered list of steps (`[[steps]]` tables). Each step has a `name` and its own options. Steps run in the order written; every step receives the result of the previous one. Unknown step names, unknown or missing options, and values of the wrong type are rejected before any image is processed.

Only the `steps` key is accepted at the top level for now.

## Steps

Steps whose name starts with `rnd_` draw random values separately for each image; the values are repeatable with `--seed`. Other steps are deterministic.

### `resize`
Scales an image keeping its proportions. Which options apply depends on `mode`:

| Mode | Result | Options |
|---|---|---|
| `longest_side` (default) | The longer side becomes `size`; the other side follows. | `size` (required) |
| `padding` | Exactly the target size: the image is fitted inside it and the free area is filled. | `size` or `width` + `height`; `fill` |
| `crop` | Exactly the target size: the image covers it completely, the overflow is cut off evenly on both sides (center-crop). | `size` or `width` + `height` |

| Option | Type | Default | Meaning |
|---|---|---|---|
| `mode` | string | `"longest_side"` | `longest_side`, `padding` or `crop`. |
| `size` | int | none | `longest_side`: target length of the longer side (required). `padding`/`crop`: shorthand for a square, `width = height = size`. Must be at least 1. |
| `width`, `height` | int | none | `padding`/`crop`: target size in pixels; give both, or use `size` instead (not both). |
| `upscale` | bool | `false` | Also enlarge images that are smaller than the target. Without it: `longest_side` leaves a small image unchanged; `padding` keeps it at its size, centered on the canvas; `crop` leaves an image unchanged if it is smaller than the target in either direction, so output sizes can vary. |
| `fill` | string | `"transparent"` | `padding` only. `transparent`, a color name such as `white`, or hex such as `#ffffff` (`#rrggbbaa` for a partly transparent fill). |

Options that a mode does not use are rejected. Transparent areas are kept only in formats that support transparency (PNG, WebP). JPEG output currently turns transparent areas black, until the output section gets a background color option; use `fill = "white"` (or another color) when the results will be JPEG.

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
