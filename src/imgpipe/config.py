import tomllib
from dataclasses import dataclass
from pathlib import Path

from imgpipe.errors import ConfigError
from imgpipe.steps import Step, create_step

# Global options of the [options] table: name -> (type, default).
OPTIONS = {"fix_orientation": (bool, True)}


@dataclass
class Config:
    steps: list[Step]
    fix_orientation: bool = True


def _load_options(path: Path, table: object) -> dict:
    """Validate the [options] table and fill in the defaults."""
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: [options] must be a table")
    unknown = sorted(set(table) - set(OPTIONS))
    if unknown:
        raise ConfigError(
            f"{path}: unknown option(s) {', '.join(unknown)} in [options]; "
            f"known options: {', '.join(OPTIONS)}"
        )
    options = {}
    for name, (expected, default) in OPTIONS.items():
        value = table.get(name, default)
        if not isinstance(value, expected):
            raise ConfigError(
                f"{path}: option '{name}' must be {expected.__name__}, "
                f"got {type(value).__name__} ({value!r})"
            )
        options[name] = value
    return options


def load_config(path: Path) -> Config:
    """Read a TOML pipeline config: the steps in file order and the global [options]."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: invalid TOML: {e}") from e

    for name in OPTIONS:
        if name in data:
            raise ConfigError(f"{path}: option '{name}' belongs in the [options] table")
    unknown = sorted(set(data) - {"steps", "options"})
    if unknown:
        raise ConfigError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")

    options = _load_options(path, data.get("options", {}))

    entries = data.get("steps")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path}: define at least one [[steps]] table")

    steps = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "name" not in entry:
            raise ConfigError(f"{path}: [[steps]] #{index} needs a 'name'")
        step_options = {key: value for key, value in entry.items() if key != "name"}
        steps.append(create_step(entry["name"], step_options))
    return Config(steps=steps, **options)
