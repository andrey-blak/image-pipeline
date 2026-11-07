"""The output section: which format files are written in, and how.

Not a pipeline step: it is applied to every image after the steps (see ``Pipeline.run``).
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from imgpipe.colors import parse_color
from imgpipe.imageio import Metadata
from imgpipe.steps import normalize_mode

DEFAULT_QUALITY = 80


@dataclass(frozen=True)
class OutputFormat:
    name: str  # as written in the preset
    pillow: str  # Pillow's format name
    extension: str  # used when converting to this format
    alpha: bool = True  # can store transparency (otherwise it is flattened onto the background)
    quality: bool = False  # takes the `quality` option
    metadata: frozenset = frozenset()  # of "exif", "xmp", "comment": carried with keep_metadata
    icc: bool = True  # the ICC color profile can be stored (it is always kept)
    rgb_only: bool = False  # accepts only RGB/RGBA pixels


FORMATS = {
    f.name: f
    for f in [
        OutputFormat("png", "PNG", ".png", metadata=frozenset({"exif"})),
        OutputFormat("jpg", "JPEG", ".jpg", alpha=False, quality=True,
                     metadata=frozenset({"exif", "xmp", "comment"})),
        OutputFormat("webp", "WEBP", ".webp", quality=True, metadata=frozenset({"exif", "xmp"}),
                     rgb_only=True),
        OutputFormat("avif", "AVIF", ".avif", quality=True, metadata=frozenset({"exif", "xmp"}),
                     rgb_only=True),
        OutputFormat("gif", "GIF", ".gif", alpha=False, metadata=frozenset({"comment"}), icc=False),
        OutputFormat("tiff", "TIFF", ".tiff"),
        OutputFormat("bmp", "BMP", ".bmp", alpha=False, icc=False),
    ]
}
ALIASES = {"jpeg": "jpg", "tif": "tiff"}
# With `format = "keep"`: Pillow's name of the source format -> table entry.
KEPT_FORMATS = {"JPEG": "jpg", "MPO": "jpg", "PNG": "png", "WEBP": "webp", "AVIF": "avif",
                "GIF": "gif", "TIFF": "tiff", "BMP": "bmp"}
EXIF_ORIENTATION_TAG = 0x0112


@dataclass
class OutputSettings:
    format: str = "keep"
    quality: int | None = None
    background: str = "white"
    keep_metadata: bool = False

    def __post_init__(self):
        name = ALIASES.get(self.format, self.format)
        if name != "keep" and name not in FORMATS:
            known = ", ".join(["keep", *FORMATS])
            raise ValueError(f"unknown format '{self.format}'; known formats: {known}")
        self.format = name
        if self.quality is not None:
            if not 1 <= self.quality <= 100:
                raise ValueError(f"'quality' must be between 1 and 100, got {self.quality}")
            if name != "keep" and not FORMATS[name].quality:
                raise ValueError(f"option 'quality' is not used by format '{name}'")
        self._background = parse_color(self.background, what="background color")
        if self._background[3] != 255:
            raise ValueError(f"'background' must be an opaque color, got {self.background!r}")

    def format_for(self, source_format: str) -> OutputFormat:
        """The format a file with the given source format is written in."""
        if self.format != "keep":
            return FORMATS[self.format]
        kept = KEPT_FORMATS.get(source_format)
        if kept:
            return FORMATS[kept]
        # Any other format (TGA, ICO, ...): saved as it is, with Pillow's defaults.
        return OutputFormat(source_format.lower(), source_format, "", icc=False)

    def target_path(self, relative: Path, source_format: str) -> Path:
        """The output path (relative to the output folder) for a source path (relative to the input)."""
        if self.format == "keep":
            return relative  # the original suffix, whatever its spelling
        return relative.with_suffix(FORMATS[self.format].extension)


def write(
    image: Image.Image,
    path: Path,
    settings: OutputSettings,
    source_format: str,
    metadata: Metadata,
    orientation_applied: bool = False,
) -> None:
    """Write an image as the output settings say."""
    fmt = settings.format_for(source_format)
    image = _prepare(image, fmt, settings._background)

    params = {}
    if fmt.quality:
        params["quality"] = settings.quality or DEFAULT_QUALITY
    if fmt.icc and metadata.icc_profile:
        params["icc_profile"] = metadata.icc_profile
    if settings.keep_metadata:
        if "exif" in fmt.metadata and metadata.exif:
            params["exif"] = _exif_for_output(metadata.exif, orientation_applied)
        if "xmp" in fmt.metadata and metadata.xmp:
            params["xmp"] = metadata.xmp
        if "comment" in fmt.metadata and metadata.comment:
            params["comment"] = metadata.comment

    path.parent.mkdir(parents=True, exist_ok=True)
    # Pillow copies some `info` entries (JPEG comment, PNG ICC profile, transparency) on its
    # own; clear them so that only what is listed in `params` is written.
    saved_info, image.info = image.info, {}
    try:
        image.save(path, format=fmt.pillow, **params)
    finally:
        image.info = saved_info


def _prepare(image: Image.Image, fmt: OutputFormat, background: tuple) -> Image.Image:
    """Bring the pixels into a mode the format can store."""
    image = normalize_mode(image)
    if image.mode in ("LA", "RGBA") and not fmt.alpha:
        base = Image.new("RGBA", image.size, background[:3] + (255,))
        return Image.alpha_composite(base, image.convert("RGBA")).convert("RGB")
    if fmt.rgb_only:
        if image.mode == "L":
            return image.convert("RGB")
        if image.mode == "LA":
            return image.convert("RGBA")
    return image


def _exif_for_output(data: bytes, orientation_applied: bool) -> Image.Exif:
    """The source EXIF; without the orientation tag when the pixels were already rotated."""
    exif = Image.Exif()
    exif.load(data)
    if orientation_applied:
        exif.pop(EXIF_ORIENTATION_TAG, None)
    return exif
