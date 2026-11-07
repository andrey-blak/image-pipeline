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

### `trim_borders`
Cuts off solid-color or transparent margins around the content (scans, screenshots, product photos on a plain background). Put it before `resize`, so the target size is reached with the margins already gone. If nothing is found, or the whole image is background, the image is left as it is.

| Option | Type | Default | Meaning |
|---|---|---|---|
| `background` | string | `"auto"` | What counts as border: `auto`, `transparent`, or a color (a name such as `white`, or hex such as `#ffffff`). |
| `tolerance` | int | `0` | 0-255. How much two colors may differ and still count as the same. The default `0` means exactly the same. Used for the border pixels (a pixel is border when it differs from the background by at most this much: the largest difference of any color channel, or for `transparent` its alpha value) and, with `background = "auto"`, for comparing the four corners. Allows for noise and compression artifacts. |

- `auto` takes the background from the four corner pixels, **but only if they agree**: no two corners may differ from each other by more than `tolerance` in any color channel (alpha included). With the default tolerance `0` they must be exactly the same color. If they do not agree there is no uniform border and nothing is cut. When they agree, the top-left corner's color is the background; if all four corners are transparent (alpha at most `tolerance`) the background is "transparent", whatever their hidden color values. Photos saved as JPEG or scanned often have slightly different corner pixels even in a white margin (for example `255,255,255` and `254,254,254`): set a `tolerance` that covers the noise, e.g. `tolerance = 5`, or name the color: `background = "#ffffff"` with a `tolerance`.
- `transparent` treats pixels whose alpha is at most `tolerance` as border. It does not look at the corners.
- A color treats pixels close to it as border, and does not look at the corners either. Transparent areas of an image with transparency count as that color. Only the color itself is used, not an alpha part.
- The cut is a rectangle: the smallest one that contains everything that is not border, so margins of different widths are all removed, and a speck in a margin keeps the margin around it.
- With `--verbose` or `--dry-run`, a `trim` entry such as `trim L12 T8 R28 B32` shows how many pixels were removed from the left, top, right and bottom (only when something was cut).

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
  - `trim`: shown only when `trim_borders` cut something: the pixels removed from the left, top, right and bottom, e.g. `trim L12 T8 R28 B32`.
  - `saturation`: the percent applied by `rnd_saturation`, or `n/a (grayscale)` when the image has no color. If several `rnd_saturation` steps are used, the values are listed separated by commas.
- `-n`, `--dry-run`: shows what would be done without writing anything (the output folder is not even created). It always prints the per-file lines described under `--verbose`.
  - Every image is read and the steps are applied, so the sizes and random values are exactly those a real run with the same `--seed` would give, and unreadable files are reported as in a real run.
  - Work that nothing later needs is skipped: for example the saturation change is not applied to the pixels when no later step reads them, and a `resize` that is the last step only reports the size it would produce instead of resampling the image.
  - A dry run does not encode or write files, so it cannot detect problems that only occur when writing (an unwritable output folder, a color mode a format cannot store).
- Files that cannot be read or processed are skipped with a warning; the batch continues. Originals are never modified.
