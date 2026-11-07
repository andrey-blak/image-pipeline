# Pipeline config

A TOML file passed with `--config`. It is separate from `pyproject.toml`. Without `--config` the tool does nothing.

The file holds an ordered list of steps (`[[steps]]` tables). Each step has a `name` and its own options. Steps run in the order written; every step receives the result of the previous one. Unknown step names, unknown or missing options, and values of the wrong type are rejected before any image is processed.

Besides the steps, the file may contain an `[options]` table with global settings. Only the `steps` and `options` keys are accepted at the top level.

## `[options]` table

Global settings go in the `[options]` table. Like any TOML table it may be written anywhere in the file: before the steps, after them, or between them. (A bare `key = value` line after a `[[steps]]` header would belong to that step, which is why the settings need their own table. A global setting written as a bare top-level key is rejected with a hint.)

```toml
[[steps]]
name = "resize"
size = 300

[options]
fix_orientation = false
```

| Option | Type | Default | Meaning |
|---|---|---|---|
| `fix_orientation` | bool | `true` | Make photos upright according to their EXIF orientation tag (phone photos are often stored sideways with a tag that tells viewers to rotate them). Done when an image is read, before any step; it is not a step. |

With `fix_orientation` on, an image with an orientation tag is rotated or mirrored so it is upright, and all steps and the `size` in `--verbose` output refer to the upright image. The written file has no orientation tag, so it is not rotated twice. Images without a tag, or with the tag "upright" (value 1), are left alone, as are unknown or damaged tag values. With `fix_orientation = false` the image is processed as stored. A dry run (`--dry-run`) applies the fix too, because it can swap width and height.

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
uv run python -m imgpipe --config config.toml [--input input] [--output output] [--seed N] [--verbose] [--dry-run]
```

- `--input` (default `input`): searched recursively for images.
- `--output` (default `output`): receives the results with the same relative paths, names and formats as the originals. This is temporary behavior until the output/naming section exists. The output folder must differ from the input folder; if it lies inside the input folder it is not rescanned.
- `--seed`: makes random values repeatable.
- `-v`, `--verbose`: prints one line to stdout for each file as soon as it is saved, with paths as given on the command line (warnings stay on stderr, the summary comes last):

  ```
  input/sub/b.jpg -> output/sub/b.jpg | size 650x470 -> 300x217 | saturation +4.2%
  ```

  - `size`: the size before and after all steps, or `WxH (unchanged)`. The "before" size is that of the upright image when the orientation was fixed.
  - `orientation`: shown only when the EXIF orientation fix changed the image, e.g. `orientation EXIF (rotated 90° cw)`. It comes right after `size`; other possible texts are `rotated 90° ccw`, `rotated 180°`, `mirrored horizontally`, `mirrored vertically`, `transposed` and `anti-transposed`.
  - `saturation`: the percent applied by `rnd_saturation`, or `n/a (grayscale)` when the image has no color. If several `rnd_saturation` steps are used, the values are listed separated by commas.
- `-n`, `--dry-run`: shows what would be done without writing anything (the output folder is not even created). It always prints the per-file lines described under `--verbose`.
  - Every image is read and the steps are applied, so the sizes and random values are exactly those a real run with the same `--seed` would give, and unreadable files are reported as in a real run.
  - Work that nothing later needs is skipped: for example the saturation change is not applied to the pixels when no later step reads them, and a `resize` that is the last step only reports the size it would produce instead of resampling the image.
  - A dry run does not encode or write files, so it cannot detect problems that only occur when writing (an unwritable output folder, a color mode a format cannot store).
- Files that cannot be read or processed are skipped with a warning; the batch continues. Originals are never modified.
