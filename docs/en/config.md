# Pipeline config

A TOML file passed with `--config`. It is separate from `pyproject.toml`. Without `--config` the tool does nothing.

The file holds an ordered list of steps (`[[steps]]` tables). Each step has a `name` and its own options. Steps run in the order written; every step receives the result of the previous one. Unknown step names, unknown or missing options, and values of the wrong type are rejected before any image is processed.

Besides the steps, the file may contain two tables of global settings: `[options]` and `[output]`. Only the `steps`, `options` and `output` keys are accepted at the top level.

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

## `[output]` table

How the results are written. It is not a pipeline step: it is applied to every image after the last step. Like `[options]`, the table may be written anywhere in the file.

```toml
[output]
format = "webp"        # keep (default), png, jpg, webp, avif, gif, tiff, bmp
quality = 85           # 1-100 (default 90), for jpg, webp and avif
background = "white"   # default; used where transparency cannot be stored
keep_metadata = false  # default
```

| Option | Type | Default | Meaning |
|---|---|---|---|
| `format` | string | `"keep"` | `keep` writes every file in its original format. Otherwise all files are converted to this format. `jpeg` and `tif` are accepted as spellings of `jpg` and `tiff`. |
| `quality` | int | `90` | 1-100. Used by `jpg`, `webp` and `avif`; with `format = "keep"` it applies to the files of those formats. Giving it for a format without a quality setting (`png`, `gif`, `tiff`, `bmp`) is an error. |
| `background` | string | `"white"` | An opaque color (a name such as `white`, or hex such as `#ffffff`) that transparent areas are flattened onto when the output format cannot store transparency. `transparent` or a color with an alpha part is rejected. |
| `keep_metadata` | bool | `false` | Carry the metadata of the original over to the result (see below). |

### Formats

| Format | Extension | Transparency | `quality` | Metadata that `keep_metadata` carries over |
|---|---|---|---|---|
| `png` | `.png` | yes | no | EXIF |
| `jpg` | `.jpg` | no, flattened | yes | EXIF, XMP, comment |
| `webp` | `.webp` | yes | yes | EXIF, XMP |
| `avif` | `.avif` | yes | yes | EXIF, XMP |
| `gif` | `.gif` | no, flattened | no | comment |
| `tiff` | `.tiff` | yes | no | none |
| `bmp` | `.bmp` | no, flattened | no | none |

- **`keep`** keeps the spelling of the original extension (`.JPG`, `.jpeg`, `.tif`). A JPEG written from a camera's multi-picture file (MPO) is saved as JPEG. Files in other formats (TGA, ICO, ...) are saved in their own format with Pillow's defaults and without metadata; if that is not possible the file is skipped with a warning.
- **Converting** changes the extension to the one in the table. Only the first frame of animated files is used.
- **Transparency** that the output format cannot store (`jpg`, `gif`, `bmp`) is composited onto `background`; semi-transparent pixels blend with it. For `png`, `webp`, `avif` and `tiff` the alpha channel is kept. Choose the background to match the page the images will be shown on.
- **Quality** 90 is used when `quality` is not given. This also applies to JPEG files in `keep` mode.

### Metadata

By default (`keep_metadata = false`) everything personal is dropped: EXIF (camera, date, GPS position, ...), XMP, comments and text chunks. The **ICC color profile is always kept** where the format can store it (`png`, `jpg`, `webp`, `avif`, `tiff`), because it is color data, not personal data, and removing it would make images with a wide-gamut profile look different.

With `keep_metadata = true`, the EXIF, XMP and comment of the original are carried over to the formats that can hold them (see the table). Notes:
- The EXIF orientation tag is removed when the pixels were rotated (`fix_orientation`), and kept when they were not (`fix_orientation = false`).
- Tags that describe the original image, such as its width and height, are not updated after resizing or trimming.
- DPI information is not carried over.

### Name clashes

When converting, two files can get the same name: `a.png` and `a.jpg` in one folder both become `a.webp`. The first file (in sorted order) keeps the name; the next ones get a number: `a-1.webp`, `a-2.webp`, and so on. Nothing is overwritten. The command line report always mentions it, with or without `--verbose`:

```
2 images processed, 0 skipped.
1 file got a number added to its name because the name was already taken:
  input/a.png -> output/a-1.webp
```

(With `--dry-run`: "would get".) With `format = "keep"` names never clash. Files left from earlier runs in the output folder are overwritten, as before.

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

Options that a mode does not use are rejected. Transparent areas are kept only in output formats that support transparency (PNG, WebP, AVIF, TIFF); for the others they are flattened onto the `background` color of the `[output]` table (white by default). Use `fill = "white"` (or another color) to have no transparency at all.

### `auto_brightness`
Adjusts brightness automatically. It is best placed after `resize` (fewer pixels to analyze) and before `rnd_saturation`. Transparency is preserved, and fully transparent pixels are ignored when measuring brightness. Brightness here means the luminance of a pixel (its gray value).

| Option | Type | Default | Meaning |
|---|---|---|---|
| `method` | string | `"autocontrast"` | `autocontrast` or `target_mean`. |
| `cutoff` | float | `0.5` | `autocontrast` only. Percent (0 to below 50) of the darkest and of the lightest pixels to ignore, so a few stray dark or bright pixels do not prevent the stretch. |
| `target` | int | `128` | `target_mean` only. The average brightness to aim for, 0-255. |
| `max_change` | float | `0.3` | `target_mean` only. The brightness factor is limited to `1 ± max_change` (0.3: between 0.7 and 1.3). Above 0, at most 1. |

Options that belong to the other method are rejected.

- `autocontrast` (levels stretch): finds the darkest and the lightest level in the image (after ignoring `cutoff` percent of the pixels at each end) and stretches that range to the full range, 0 to 255. The same adjustment is applied to every color channel, so the colors keep their balance and no color cast is removed or added. An image that already uses the full range, or has a single brightness, is left as it is.
- `target_mean`: scales the brightness so that the average comes closer to `target`: every pixel is multiplied by `target / average`, but by no more than `max_change` up or down. The result can end up away from `target` when the factor is limited or bright pixels are clipped at white. An image that is already at the target, or is completely black, is left as it is.
- With `--verbose` or `--dry-run`, a `brightness` entry shows what was done, only when something changed: `brightness levels 18-231 -> 0-255` (the levels that were stretched), or `brightness x1.16 (mean 110, target 128)` for `target_mean` (the factor and the average before; `, limited` is added when `max_change` held the factor back).

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
- `--output` (default `output`): receives the results with the same relative paths (subfolders are mirrored). Names and formats come from the `[output]` table: by default they are the originals'; with a `format` the extension changes and name clashes get a number. Renaming files by a pattern (date and time with random digits) is not implemented yet. The output folder must differ from the input folder; if it lies inside the input folder it is not rescanned.
- `--seed`: makes random values repeatable.
- `-v`, `--verbose`: prints one line to stdout for each file as soon as it is saved, with paths as given on the command line (warnings stay on stderr, the summary comes last):

  ```
  input/sub/b.jpg -> output/sub/b.jpg | size 650x470 -> 300x217 | saturation +4.2%
  ```

  - `size`: the size before and after all steps, or `WxH (unchanged)`. The "before" size is that of the upright image when the orientation was fixed.
  - `orientation`: shown only when the EXIF orientation fix changed the image, e.g. `orientation EXIF (rotated 90° cw)`. It comes right after `size`; other possible texts are `rotated 90° ccw`, `rotated 180°`, `mirrored horizontally`, `mirrored vertically`, `transposed` and `anti-transposed`.
  - `trim`: shown only when `trim_borders` cut something: the pixels removed from the left, top, right and bottom, e.g. `trim L12 T8 R28 B32`.
  - `brightness`: shown only when `auto_brightness` changed something, e.g. `brightness levels 18-231 -> 0-255` or `brightness x1.16 (mean 110, target 128)`.
  - `saturation`: the percent applied by `rnd_saturation`, or `n/a (grayscale)` when the image has no color. If several `rnd_saturation` steps are used, the values are listed separated by commas.
- `-n`, `--dry-run`: shows what would be done without writing anything (the output folder is not even created). It always prints the per-file lines described under `--verbose`.
  - Every image is read and the steps are applied, so the sizes and random values are exactly those a real run with the same `--seed` would give, and unreadable files are reported as in a real run.
  - Work that nothing later needs is skipped: for example the saturation change is not applied to the pixels when no later step reads them, and a `resize` that is the last step only reports the size it would produce instead of resampling the image.
  - A dry run does not encode or write files, so it cannot detect problems that only occur when writing (an unwritable output folder, a color mode a format cannot store).
- Files that cannot be read or processed are skipped with a warning; the batch continues. Originals are never modified.
