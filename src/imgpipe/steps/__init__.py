"""Pipeline steps and their registry.

A step is a dataclass whose fields are its config options. Register it with
``@register("name")``; the name is what the config file refers to.
"""

import dataclasses
import random
import types
import typing
from dataclasses import dataclass, field

from PIL import Image

from imgpipe.errors import ConfigError

REGISTRY: dict[str, type["Step"]] = {}


@dataclass
class Context:
    """Per-run state shared by all steps. Random values are drawn from ``rng``.

    ``changes`` collects what the steps applied to the current image (for the
    verbose report); steps add entries with ``record``.

    In a dry run the pipeline sets, before each step, what that step may skip
    because no later step needs it: ``skip_pixels`` (the pixel work) and
    ``skip_resize`` (changing the image size). A step that skips its size change
    reports the size it would have produced with ``record_size``. Steps may ignore
    the flags and always do their work.
    """

    rng: random.Random
    changes: dict[str, str] = field(default_factory=dict)
    skip_pixels: bool = False
    skip_resize: bool = False
    reported_size: tuple[int, int] | None = None

    def record_size(self, size: tuple[int, int]) -> None:
        self.reported_size = size

    def record(self, key: str, text: str) -> None:
        """Note an applied change; recording the same key again appends to it."""
        self.changes[key] = f"{self.changes[key]}, {text}" if key in self.changes else text


class Step:
    """Base class for pipeline steps. Subclasses must also be dataclasses.

    ``depends_on_pixels`` / ``depends_on_size``: whether the step's result (the size
    it produces, the values it records) needs the incoming image's pixels (including
    its mode, i.e. color type) / size.
    A dry run uses them to skip earlier work that no later step needs. They default
    to True, so a step that does not declare them is never skipped over.
    """

    name: typing.ClassVar[str]
    depends_on_pixels: typing.ClassVar[bool] = True
    depends_on_size: typing.ClassVar[bool] = True

    @classmethod
    def from_options(cls, options: dict[str, typing.Any]) -> "Step":
        fields = {f.name: f for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        hints = typing.get_type_hints(cls)
        unknown = sorted(set(options) - set(fields))
        if unknown:
            raise ConfigError(
                f"step '{cls.name}': unknown option(s) {', '.join(unknown)}; "
                f"known options: {', '.join(fields) or 'none'}"
            )
        for key, field in fields.items():
            required = (
                field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING
            )
            if key not in options:
                if required:
                    raise ConfigError(f"step '{cls.name}': missing required option '{key}'")
                continue
            _check_type(cls.name, key, options[key], hints[key])
        try:
            return cls(**options)
        except ConfigError:
            raise
        except ValueError as e:
            raise ConfigError(f"step '{cls.name}': {e}") from e

    def apply(self, image: Image.Image, ctx: Context) -> Image.Image:
        raise NotImplementedError


def _check_type(step: str, key: str, value: typing.Any, expected: type) -> None:
    if typing.get_origin(expected) in (typing.Union, types.UnionType):
        # `X | None` marks an optional option; TOML has no null, so check against X.
        (expected,) = (arg for arg in typing.get_args(expected) if arg is not type(None))
    if expected is float:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
    else:
        ok = isinstance(value, expected)
    if not ok:
        raise ConfigError(
            f"step '{step}': option '{key}' must be {expected.__name__}, "
            f"got {type(value).__name__} ({value!r})"
        )


def register(name: str):
    def decorator(cls: type[Step]) -> type[Step]:
        if name in REGISTRY:
            raise ValueError(f"step '{name}' is already registered")
        cls.name = name
        REGISTRY[name] = cls
        return cls

    return decorator


def create_step(name: str, options: dict[str, typing.Any]) -> Step:
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise ConfigError(
            f"unknown step '{name}'; known steps: {', '.join(sorted(REGISTRY))}"
        ) from None
    return cls.from_options(options)


def normalize_mode(image: Image.Image) -> Image.Image:
    """Convert exotic modes (palette, CMYK, 16-bit, ...) to ones steps can handle."""
    if image.mode in ("RGB", "RGBA", "L", "LA"):
        return image
    has_alpha = image.mode in ("PA", "RGBa", "La") or "transparency" in image.info
    return image.convert("RGBA" if has_alpha else "RGB")


# Import for the side effect of registering the built-in steps.
from imgpipe.steps import resize, rnd_saturation  # noqa: E402,F401
