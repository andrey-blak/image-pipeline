import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from imgpipe.errors import ConfigError
from imgpipe.output import OutputSettings
from imgpipe.steps import Step, create_step

# Tables of global settings: name -> option name -> expected type.
OPTIONS = {"fix_orientation": bool}
OUTPUT = {"format": str, "quality": int, "background": str, "keep_metadata": bool}
TABLES = {"options": OPTIONS, "output": OUTPUT}


@dataclass
class Config:
    steps: list[Step]
    fix_orientation: bool = True
    output: OutputSettings = field(default_factory=OutputSettings)


def _load_table(path: Path, section: str, table: object, spec: dict[str, type]) -> dict:
    """Check a table of global settings; returns the values that were given."""
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: [{section}] must be a table")
    unknown = sorted(set(table) - set(spec))
    if unknown:
        raise ConfigError(
            f"{path}: unknown option(s) {', '.join(unknown)} in [{section}]; "
            f"known options: {', '.join(spec)}"
        )
    for name, value in table.items():
        expected = spec[name]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise ConfigError(
                f"{path}: option '{name}' must be {expected.__name__}, "
                f"got {type(value).__name__} ({value!r})"
            )
    return dict(table)


def load_config(path: Path) -> Config:
    """Read a TOML pipeline config: the steps in file order and the global tables."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: invalid TOML: {e}") from e

    for section, spec in TABLES.items():
        for name in spec:
            if name in data:
                raise ConfigError(f"{path}: option '{name}' belongs in the [{section}] table")
    unknown = sorted(set(data) - {"steps", *TABLES})
    if unknown:
        raise ConfigError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")

    options = _load_table(path, "options", data.get("options", {}), OPTIONS)
    output_values = _load_table(path, "output", data.get("output", {}), OUTPUT)
    try:
        output = OutputSettings(**output_values)
    except ValueError as e:
        raise ConfigError(f"{path}: [output]: {e}") from e

    entries = data.get("steps")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path}: define at least one [[steps]] table")

    steps = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "name" not in entry:
            raise ConfigError(f"{path}: [[steps]] #{index} needs a 'name'")
        step_options = {key: value for key, value in entry.items() if key != "name"}
        steps.append(create_step(entry["name"], step_options))
    return Config(steps=steps, output=output, **options)
