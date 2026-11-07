import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from imgpipe import imageio, output
from imgpipe.errors import ConfigError
from imgpipe.output import OutputSettings
from imgpipe.steps import Context, Step


@dataclass
class FileReport:
    """What happened to one file. ``source``/``target`` are relative to the input/output folders."""

    source: Path
    target: Path
    changes: dict[str, str]


@dataclass
class RunResult:
    processed: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    # (source, final target), both relative to their folders, for files whose output name
    # was already taken by an earlier file and got a number added.
    renamed: list[tuple[Path, Path]] = field(default_factory=list)


def _free_name(path: Path, used: set[Path]) -> Path:
    """``path``, or ``stem-1.ext``, ``stem-2.ext``, ... if the name is already in ``used``."""
    candidate, number = path, 0
    while candidate in used:
        number += 1
        candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
    return candidate


def _size_change(before: tuple[int, int], after: tuple[int, int]) -> str:
    old, new = "x".join(map(str, before)), "x".join(map(str, after))
    return f"{old} (unchanged)" if before == after else f"{old} -> {new}"


class Pipeline:
    def __init__(
        self,
        steps: list[Step],
        fix_orientation: bool = True,
        output_settings: OutputSettings | None = None,
    ):
        self.steps = steps
        self.fix_orientation = fix_orientation
        self.output = output_settings or OutputSettings()

    def process(self, image: Image.Image, ctx: Context, dry_run: bool = False) -> Image.Image:
        """Run the steps in order.

        In a dry run each step is told what it may skip: its pixel work if no later
        step depends on pixels, its size change if no later step depends on size.
        """
        for index, step in enumerate(self.steps):
            later = self.steps[index + 1 :]
            ctx.skip_pixels = dry_run and not any(s.depends_on_pixels for s in later)
            ctx.skip_resize = dry_run and not any(s.depends_on_size for s in later)
            image = step.apply(image, ctx)
        ctx.skip_pixels = ctx.skip_resize = False
        return image

    def run(
        self,
        input_dir: Path,
        output_dir: Path,
        rng: random.Random,
        on_file: Callable[[FileReport], None] | None = None,
        dry_run: bool = False,
    ) -> RunResult:
        """Process every image under ``input_dir`` into the mirrored path under ``output_dir``.

        Originals are never modified. Files that cannot be read or processed are
        recorded in ``skipped`` and the batch continues. ``on_file`` is called with a
        ``FileReport`` right after each file is saved. With ``dry_run`` nothing is
        written (``processed`` then lists the would-be targets) and work that no later
        step needs is skipped; the reports stay the same as in a real run.

        The output name and format come from the output settings. If conversion gives two
        files the same name, the later one gets a number (``a-1.webp``); see ``renamed``.
        """
        input_dir, output_dir = input_dir.resolve(), output_dir.resolve()
        if output_dir == input_dir:
            raise ConfigError("output folder must differ from the input folder")
        ctx = Context(rng=rng)
        result = RunResult()
        used: set[Path] = set()
        for source in imageio.find_images(input_dir, exclude=output_dir):
            relative = source.relative_to(input_dir)
            ctx.changes = {}
            ctx.reported_size = None
            try:
                loaded = imageio.load(source)
                image = loaded.image
                oriented = None
                if self.fix_orientation:
                    # Not a step: always first. Also in a dry run, as it can swap width and height.
                    image, oriented = imageio.fix_orientation(image, loaded.orientation)
                processed = self.process(image, ctx, dry_run)
                wanted = self.output.target_path(relative, loaded.format)
                final = _free_name(wanted, used)
                if not dry_run:
                    output.write(
                        processed, output_dir / final, self.output, loaded.format,
                        loaded.metadata, orientation_applied=bool(oriented),
                    )
            except Exception as e:  # one bad file must not stop the batch
                result.skipped.append((source, f"{type(e).__name__}: {e}"))
            else:
                used.add(final)
                result.processed.append(output_dir / final)
                if final != wanted:
                    result.renamed.append((relative, final))
                if on_file is not None:
                    size = ctx.reported_size or processed.size
                    changes = {"size": _size_change(image.size, size)}
                    if oriented:
                        changes["orientation"] = f"EXIF ({oriented})"
                    changes |= ctx.changes
                    on_file(FileReport(source=relative, target=final, changes=changes))
        return result
