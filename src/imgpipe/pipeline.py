import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from imgpipe import imageio
from imgpipe.errors import ConfigError
from imgpipe.steps import Context, Step


@dataclass
class RunResult:
    processed: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


class Pipeline:
    def __init__(self, steps: list[Step]):
        self.steps = steps

    def process(self, image: Image.Image, ctx: Context) -> Image.Image:
        for step in self.steps:
            image = step.apply(image, ctx)
        return image

    def run(self, input_dir: Path, output_dir: Path, rng: random.Random) -> RunResult:
        """Process every image under ``input_dir`` into the mirrored path under ``output_dir``.

        Originals are never modified. Files that cannot be read or processed are
        recorded in ``skipped`` and the batch continues.
        """
        input_dir, output_dir = input_dir.resolve(), output_dir.resolve()
        if output_dir == input_dir:
            raise ConfigError("output folder must differ from the input folder")
        ctx = Context(rng=rng)
        result = RunResult()
        for source in imageio.find_images(input_dir, exclude=output_dir):
            target = output_dir / source.relative_to(input_dir)
            try:
                image, fmt = imageio.load(source)
                imageio.save(self.process(image, ctx), target, fmt)
            except Exception as e:  # one bad file must not stop the batch
                result.skipped.append((source, f"{type(e).__name__}: {e}"))
            else:
                result.processed.append(target)
        return result
