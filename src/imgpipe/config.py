import tomllib
from pathlib import Path

from imgpipe.errors import ConfigError
from imgpipe.steps import Step, create_step


def load_steps(path: Path) -> list[Step]:
    """Read a TOML pipeline config and build its steps, in file order."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: invalid TOML: {e}") from e

    unknown = sorted(set(data) - {"steps"})
    if unknown:
        raise ConfigError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")

    entries = data.get("steps")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path}: define at least one [[steps]] table")

    steps = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "name" not in entry:
            raise ConfigError(f"{path}: [[steps]] #{index} needs a 'name'")
        options = {key: value for key, value in entry.items() if key != "name"}
        steps.append(create_step(entry["name"], options))
    return steps
