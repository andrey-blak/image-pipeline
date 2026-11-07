# Pipeline preset

A TOML file passed with `--preset`. Without `--preset` the tool does nothing.

**Writing values.** Text values are written in double quotes: `format = "jpg"`, `name = "resize"`. Numbers and `true`/`false` are written without quotes: `quality = 80`, `keep_metadata = false`. Lines starting with `#` are comments. In this document a value in quotes is text you type with the quotes.

The file holds an ordered list of steps (each one is a `[[steps]]` entry). Each step has a `name` and its own options. Steps run in the order written; every step receives the result of the previous one. Unknown step names, unknown or missing options, and values of the wrong type are rejected before any image is processed.

At least one step is required, unless the global sections alone change the files. Then the steps may be left out (or `steps = []`) and the images are only renamed, converted, re-saved or have their EXIF orientation applied. That is the case when the file has any of:

- a `[rename]` section;
- `format` in `[output]` other than `"keep"`;
- `quality` in `[output]`;
- `keep_metadata = false` written in `[output]` (it is the default, so it counts only when written; `keep_metadata = true` does not count);
- `exif_orientation = "apply"` or `"remove"` written in `[options]`.

`background` alone counts for nothing. Without steps and without one of these the file is rejected.

Besides the steps, the file may contain three sections of global settings (a section is a group of settings under a `[name]` header): `[options]`, `[output]` and `[rename]`. Only the `steps`, `options`, `output` and `rename` keys are accepted at the top level.

## `[options]` section

Global settings go in the `[options]` section. Like any section it may be written anywhere in the file: before the steps, after them, or between them. (A bare `key = value` line after a `[[steps]]` header would belong to that step, which is why the settings need their own section. A global setting written as a bare top-level key is rejected with a hint.)

```toml
[[steps]]
name = "resize"
size = 300

[options]
exif_orientation = "keep"
```

| Option | Type | Default | Meaning |
|---|---|---|---|
| `exif_orientation` | string | `"apply"` | What to do with the EXIF orientation tag of photos (phone photos are often stored sideways with a tag that tells viewers to rotate them): `"apply"`, `"keep"` or `"remove"`. Done when an image is read, before any step. |

The values:

- `"apply"` (default): an image with an orientation tag is rotated or mirrored so it is upright, and the tag is reset (removed from the written file, so the photo is not rotated twice). All steps and the `size` in `--verbose` output refer to the upright image.
- `"keep"`: the pixels stay as stored and the tag is written to the output as it is. This is an exception to the metadata stripping: the orientation tag is written even with `keep_metadata = false` (then it is the only EXIF tag written). Only formats that can hold EXIF can carry it (`"png"`, `"jpg"`, `"webp"`, `"avif"`); `"gif"`, `"bmp"` and `"tiff"` lose it. The steps still work on the photo as it is shown: `width` and `height` of `resize` are those of the shown photo (the stored pixels are exchanged for the tags 5-8), and `rotate`/`rnd_rotate` turn the shown photo in the stated direction (for the mirrored tags 2, 4, 5, 7 the stored pixels are turned the other way). The tag therefore stays correct. The sizes in `--verbose` output are those of the stored pixels.
- `"remove"`: the pixels stay as stored and the tag is removed. Viewers show the photo as stored, never rotated.

Images without a tag, or with the tag "upright" (value 1), are left alone, as are unknown or damaged tag values. A dry run (`--dry-run`) follows the same rule, because `"apply"` can swap width and height.

## `[output]` section

How the results are written. It is not a pipeline step: it is applied to every image after the last step. Like `[options]`, the section may be written anywhere in the file.

```toml
[output]
format = "webp"        # "keep" (default), "png", "jpg", "webp", "avif", "gif", "tiff", "bmp"
quality = 85           # 1-100 (default 80), for "jpg", "webp" and "avif"
background = "white"   # default; used where transparency cannot be stored
keep_metadata = false  # default
```

| Option | Type | Default | Meaning |
|---|---|---|---|
| `format` | string | `"keep"` | `"keep"` writes every file in its original format. Otherwise all files are converted to this format, e.g. `"jpg"`. `"jpeg"` and `"tif"` are accepted as spellings of `"jpg"` and `"tiff"`. |
| `quality` | int | `80` | 1-100. Used by `jpg`, `webp` and `avif`; with `format = "keep"` it applies to the files of those formats. Giving it for a format without a quality setting (`png`, `gif`, `tiff`, `bmp`) is an error. |
| `background` | string | `"white"` | An opaque color (a name such as `"white"`, or hex such as `"#ffffff"`) that transparent areas are flattened onto when the output format cannot store transparency. `"transparent"` or a color with an alpha part is rejected. |
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
- **Quality** 80 is used when `quality` is not given. This also applies to JPEG files in `keep` mode.

### Metadata

By default (`keep_metadata = false`) everything personal is dropped: EXIF (camera, date, GPS position, ...), XMP, comments and text chunks. The **ICC color profile is always kept** where the format can store it (`png`, `jpg`, `webp`, `avif`, `tiff`), because it is color data, not personal data, and removing it would make images with a wide-gamut profile look different.

With `keep_metadata = true`, the EXIF, XMP and comment of the original are carried over to the formats that can hold them (see the table). Notes:
- The EXIF orientation tag is removed when the pixels were rotated or when `exif_orientation = "remove"`, and kept with `exif_orientation = "keep"` (even with `keep_metadata = false`, see `[options]`).
- Tags that describe the original image, such as its width and height, are not updated after resizing or trimming.
- DPI information is not carried over.

### Name clashes

When converting, two files can get the same name: `a.png` and `a.jpg` in one folder both become `a.webp`. The first file (in sorted order) keeps the name; the next ones get a number: `a-1.webp`, `a-2.webp`, and so on. Nothing is overwritten. The command line report always mentions it, with or without `--verbose`:

```
2 images processed, 0 skipped.
1 file got a number added to its name because the name was already taken:
  input/a.png -> output/a-1.webp
```

(With `--dry-run`: "would get".) With `format = "keep"` and no `[rename]` names never clash. Files left from earlier runs in the output folder are overwritten, as before.

## `[rename]` section

Gives the result files new names built from a pattern. Like `[output]` it is not a pipeline step, it is applied last, and the section may be written anywhere in the file. Without it the files keep their names. The new name has no connection to the original unless the pattern says so (`N`).

```toml
[rename]
pattern = "N-YYYY-MM-dd-HHmmssSSS-CCC-RRaaAALLBB"
# counter_start = 1
```

| Option | Type | Default | Meaning |
|---|---|---|---|
| `pattern` | string | required | The file name without its extension, built from the tokens below. |
| `counter_start` | int | `1` | The first value of the counter `C` (not negative). |

The pattern gives only the name. The extension is added automatically: the original one (as spelled) with `format = "keep"`, or the extension of the new format. Subfolders are mirrored as usual; only the file name changes. If two files get the same name, the later one gets a number (see [Name clashes](#name-clashes)).

### Tokens

A token is a run of the same letter; how many times it is repeated matters. The tokens follow Java's `DateTimeFormatter`. For numbers, one letter means "as many digits as needed, no padding"; more letters mean a zero-padded field of that width.

| Token | Meaning | Examples |
|---|---|---|
| `N` | original file name without the extension | `Holiday` |
| `E` | original extension, as spelled, without the dot (empty if none) | `jpg` |
| `Y` | year: `YYYY` four digits, `YY` two digits | `2023`, `23` |
| `M` | month: `M`, `MM` | `8`, `08` |
| `d` | day of month: `d`, `dd` | `5`, `05` |
| `H` | hour of day, 0-23: `H`, `HH` | `14` |
| `h` | clock hour, 1-12: `h`, `hh` (there is no AM/PM marker) | `2`, `02` |
| `m` | minute: `m`, `mm` | `3`, 03` |
| `s` | second: `s`, `ss` | `9`, `09` |
| `S` | fraction of a second: `S` tenths, `SS` hundredths, `SSS` milliseconds | `8`, `87`, `874` |
| `C` | counter: `C` no padding, `CCC` at least three digits | `7`, `007` |
| `R` | random digits (0-9), one per letter | `8`, `3` |
| `A` | random uppercase letters (A-Z) | `K`, `J`, `X` |
| `a` | random lowercase letters (a-z) | `k`, `j`, `x` |
| `L` | random letters of both cases | `K`, `j`, `X` |
| `B` | random digits and letters | `A`, `7`, `k` |
| `U` | UUID (random, version 4) | `8be4df61-93ca-41d2-aa0d-00e098032b8c` |

Notes:

- An empty pattern is rejected.
- Allowed repeat counts: `N`, `E`, `U` once; `Y` two or four; `M`, `d`, `H`, `h`, `m`, `s` once or twice; `S` one to three; `C` and the random tokens any number. Anything else is rejected.
- The date and time are the **processing time** of each file. In a dry run the names show the dry run's own time.
- The counter counts the files written in this run in processing order, starting at `counter_start`; a file that could not be processed does not use a number. The counter is not reset in subfolders.
- Random parts and UUIDs come from the same generator as the random steps, so `--seed` makes them repeatable.
- **Other letters are copied as they are**, so `photo_` works. But any token letter is a token: `IMG_` is read as `I`, the month, `G_`. Put literal text in single quotes: `'IMG_'CCC` gives `IMG_007`. Inside quotes `''` is one quote (`'it''s'` gives `it's`), and `''` outside quotes is also one quote.
- The literal text must not contain `/ \ : * ? " < > |`.
- A pattern without random parts or a counter or the original name makes every file the same name, and the clash numbering (`-1`, `-2`, ...) then separates them.

## Steps

Steps whose name starts with `rnd_` draw random values separately for each image; the values are repeatable with `--seed`. Other steps are deterministic.

### `trim_borders`
Cuts off solid-color or transparent margins around the content (scans, screenshots, product photos on a plain background). Put it before `resize`, so the target size is reached with the margins already gone. If nothing is found, or the whole image is background, the image is left as it is.

| Option | Type | Default | Meaning |
|---|---|---|---|
| `background` | string | `"auto"` | What counts as border: `"auto"`, `"transparent"`, or a color (a name such as `"white"`, or hex such as `"#ffffff"`). |
| `tolerance` | int | `0` | 0-255. How much two colors may differ and still count as the same. The default `0` means exactly the same. Used for the border pixels (a pixel is border when it differs from the background by at most this much: the largest difference of any color channel, or for `transparent` its alpha value) and, with `background = "auto"`, for comparing the four corners. Allows for noise and compression artifacts. |

- `"auto"` takes the background from the four corner pixels, **but only if they agree**: no two corners may differ from each other by more than `tolerance` in any color channel (alpha included). With the default tolerance `0` they must be exactly the same color. If they do not agree there is no uniform border and nothing is cut. When they agree, the top-left corner's color is the background; if all four corners are transparent (alpha at most `tolerance`) the background is "transparent", whatever their hidden color values. Photos saved as JPEG or scanned often have slightly different corner pixels even in a white margin (for example `255,255,255` and `254,254,254`): set a `tolerance` that covers the noise, e.g. `tolerance = 5`, or name the color: `background = "#ffffff"` with a `tolerance`.
- `"transparent"` treats pixels whose alpha is at most `tolerance` as border. It does not look at the corners.
- A color treats pixels close to it as border, and does not look at the corners either. Transparent areas of an image with transparency count as that color. Only the color itself is used, not an alpha part.
- The cut is a rectangle: the smallest one that contains everything that is not border, so margins of different widths are all removed, and a speck in a margin keeps the margin around it.
- With `--verbose` or `--dry-run`, a `trim` entry such as `trim L12 T8 R28 B32` shows how many pixels were removed from the left, top, right and bottom (only when something was cut).

### `rotate`
Rotates by a fixed angle. For a random angle use `rnd_rotate`. A good place in a pipeline: after `trim_borders` and before `resize`.

| Option | Type | Default | Meaning |
|---|---|---|---|
| `angle` | float | required | Degrees. **Positive turns clockwise**, negative counterclockwise. Any number is accepted. |
| `corners` | string | `"crop"` | What to do with the empty corners that a tilted picture leaves: `"crop"` or `"fill"` (see below). |
| `fill` | string | `"transparent"` | `corners = "fill"` only. `"transparent"`, a color name such as `"white"`, or hex such as `"#ffffff"` (`"#rrggbbaa"` for a partly transparent fill). Rejected with `crop`. |

- **Exact turns:** multiples of 90 degrees (`90`, `180`, `-90`, `270`, ...) are lossless turns with no empty corners, so `corners` and `fill` make no difference. A multiple of 360 (including `0`) does nothing.
- **`corners = "crop"`** cuts away the empty corners: the result is the largest rectangle, centered, with the same proportions as the original, that lies completely inside the rotated picture. A little of the picture is lost at the edges (for a 100x60 picture the width and height shrink by about 3% at 1°, 12% at 5° and 21% at 10°); the size shrinks accordingly, and a later `resize` brings it to the target. Nothing but picture is left in the result, with no filled or transparent corners.
- **`corners = "fill"`** keeps the whole picture on a larger canvas, just big enough to hold it, and fills the corners with `fill`. With the default `transparent` fill the result has an alpha channel (flattened onto the `[output]` `background` when the output format has no transparency, such as JPEG). A color without transparency keeps images without alpha as they are. Edges of the rotated picture are not smoothed.
- With `--verbose` or `--dry-run`, a `rotation` entry shows the angle, e.g. `rotation +90°` or `rotation -12.5°` (nothing when the angle is a multiple of 360).

### `rnd_rotate`
Rotates by a random angle, drawn separately for each image (repeatable with `--seed`). Corners are handled as in `rotate`.

| Option | Type | Default | Meaning |
|---|---|---|---|
| `min_angle` | float | `0` | Smallest angle in degrees, an absolute value: `0` or more. |
| `max_angle` | float | `5` | Largest angle in degrees, an absolute value: at most `180`, not less than `min_angle`. |
| `corners`, `fill` | | `"crop"`, `"transparent"` | As in `rotate`. |

The size of the angle is drawn uniformly between `min_angle` and `max_angle`, and the direction, clockwise or counterclockwise, is chosen at random with equal probability. So the default `0` to `5` means "up to 5° either way", and `min_angle = 2, max_angle = 5` means "between 2° and 5°, either way" (never less than 2°). With `min_angle = max_angle` the angle is always that size, in a random direction. With `0` and `0` nothing is rotated. The `rotation` entry in the `--verbose` / `--dry-run` line shows the angle drawn, e.g. `rotation +3.2°` (positive: clockwise).

### `resize`
Scales an image keeping its proportions. Which options apply depends on `mode`:

| Mode | Result | Options |
|---|---|---|
| `"longest_side"` (default) | The longer side becomes `size`; the other side follows. | `size` (required) |
| `"scale"` | Exactly one side is set (`width` or `height`); the other side follows, keeping the proportions. | `width` or `height` (exactly one) |
| `"padding"` | Exactly the target size: the image is fitted inside it and the free area is filled. | `size` or `width` + `height`; `fill` |
| `"crop"` | Exactly the target size: the image covers it completely, the overflow is cut off evenly on both sides (center-crop). | `size` or `width` + `height` |

| Option | Type | Default | Meaning |
|---|---|---|---|
| `mode` | string | `"longest_side"` | `"longest_side"`, `"scale"`, `"padding"` or `"crop"`. |
| `size` | int | none | `longest_side`: target length of the longer side (required). `padding`/`crop`: shorthand for a square, `width = height = size`. Must be at least 1. |
| `width`, `height` | int | none | `scale`: give exactly one; the other side follows (rounded, at least 1). `padding`/`crop`: target size in pixels; give both, or use `size` instead (not both). |
| `upscale` | bool | `true` | Images smaller than the target are enlarged too. With `upscale = false`: `longest_side` and `scale` leave a small image unchanged; `padding` keeps it at its size, centered on the canvas; `crop` leaves an image unchanged if it is smaller than the target in either direction, so output sizes can vary. |
| `fill` | string | `"transparent"` | `padding` only. `"transparent"`, a color name such as `"white"`, or hex such as `"#ffffff"` (`"#rrggbbaa"` for a partly transparent fill). |

Options that a mode does not use are rejected. Transparent areas are kept only in output formats that support transparency (PNG, WebP, AVIF, TIFF); for the others they are flattened onto the `background` color of the `[output]` section (white by default). Use `fill = "white"` (or another color) to have no transparency at all.

### `auto_brightness`
Adjusts brightness automatically. It is best placed after `resize` (fewer pixels to analyze) and before `rnd_saturation`. Transparency is preserved, and fully transparent pixels are ignored when measuring brightness. Brightness here means the luminance of a pixel (its gray value).

| Option | Type | Default | Meaning |
|---|---|---|---|
| `method` | string | `"autocontrast"` | `"autocontrast"` or `"target_mean"`. |
| `cutoff` | float | `0.5` | `autocontrast` only. Percent (0 to below 50) of the darkest and of the lightest pixels to ignore, so a few stray dark or bright pixels do not prevent the stretch. |
| `target` | int | `128` | `target_mean` only. The average brightness to aim for, 0-255. |
| `max_change` | float | `0.3` | `target_mean` only. The brightness factor is limited to `1 ± max_change` (0.3: between 0.7 and 1.3). Above 0, at most 1. |

Options that belong to the other method are rejected.

- `"autocontrast"` (levels stretch): finds the darkest and the lightest level in the image (after ignoring `cutoff` percent of the pixels at each end) and stretches that range to the full range, 0 to 255. The same adjustment is applied to every color channel, so the colors keep their balance and no color cast is removed or added. An image that already uses the full range, or has a single brightness, is left as it is.
- `"target_mean"`: scales the brightness so that the average comes closer to `target`: every pixel is multiplied by `target / average`, but by no more than `max_change` up or down. The result can end up away from `target` when the factor is limited or bright pixels are clipped at white. An image that is already at the target, or is completely black, is left as it is.
- With `--verbose` or `--dry-run`, a `brightness` entry shows what was done, only when something changed: `brightness levels 18-231 -> 0-255` (the levels that were stretched), or `brightness x1.16 (mean 110, target 128)` for `target_mean` (the factor and the average before; `, limited` is added when `max_change` held the factor back).

### `rnd_saturation`
Changes saturation by a random percent in `[min_percent, max_percent]`, drawn separately for each image (repeatable with `--seed`). Transparency is preserved. Grayscale images are left unchanged.

| Option | Type | Default | Meaning |
|---|---|---|---|
| `min_percent` | float | required | Lower bound, e.g. `3` for +3%. Must be above -100. |
| `max_percent` | float | required | Upper bound; not less than `min_percent`. |

## Command line

```
uv run python -m imgpipe --preset preset.toml [--input input] [--output output] [--seed N] [--verbose | --quiet] [--dry-run]
```

By default one progress line is printed to stdout for each file as soon as it is saved, with paths as given on the command line, and a summary at the end (warnings stay on stderr):

```
input/sub/b.jpg -> output/sub/b.jpg
...
2 images processed, 0 skipped.
```

- `--input` (default `input`): searched recursively for images.
- `--output` (default `output`): receives the results with the same relative paths (subfolders are mirrored). Names and formats come from the `[output]` section: by default they are the originals'; with a `format` the extension changes and name clashes get a number. Renaming files by a pattern (date and time with random digits) is not implemented yet. The output folder must differ from the input folder; if it lies inside the input folder it is not rescanned.
- `--seed`: makes random values repeatable.
- `-v`, `--verbose`: adds what was applied to each progress line:

  ```
  input/sub/b.jpg -> output/sub/b.jpg | size 650x470 -> 300x217 | saturation +4.2%
  ```

  - `size`: the size before and after all steps, or `WxH (unchanged)`. The "before" size is that of the upright image when the orientation was applied.
  - `orientation`: shown only when the EXIF orientation was applied and changed the image, e.g. `orientation EXIF (rotated 90° cw)`. It comes right after `size`; other possible texts are `rotated 90° ccw`, `rotated 180°`, `mirrored horizontally`, `mirrored vertically`, `transposed` and `anti-transposed`.
  - `trim`: shown only when `trim_borders` cut something: the pixels removed from the left, top, right and bottom, e.g. `trim L12 T8 R28 B32`.
  - `brightness`: shown only when `auto_brightness` changed something, e.g. `brightness levels 18-231 -> 0-255` or `brightness x1.16 (mean 110, target 128)`.
  - `saturation`: the percent applied by `rnd_saturation`, or `n/a (grayscale)` when the image has no color. If several `rnd_saturation` steps are used, the values are listed separated by commas.
- `-q`, `--quiet`: prints no progress lines and no summary, so a successful run is silent. Warnings about skipped files and errors are still shown, and so is the notice about files that got a number added to their names (you did not choose those names). Cannot be combined with `--verbose` or `--dry-run`.
- `-n`, `--dry-run`: shows what would be done without writing anything (the output folder is not even created). It always prints the per-file lines described under `--verbose`.
  - Every image is read and the steps are applied, so the sizes and random values are exactly those a real run with the same `--seed` would give, and unreadable files are reported as in a real run.
  - Work that nothing later needs is skipped: for example the saturation change is not applied to the pixels when no later step reads them, and a `resize` that is the last step only reports the size it would produce instead of resampling the image.
  - A dry run does not encode or write files, so it cannot detect problems that only occur when writing (an unwritable output folder, a color mode a format cannot store).
- Files that cannot be read or processed are skipped with a warning; the batch continues. Originals are never modified.
