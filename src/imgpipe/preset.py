import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from imgpipe.errors import PresetError
from imgpipe.naming import RenameSettings
from imgpipe.output import OutputSettings
from imgpipe.steps import Step, create_step

# Sections of global settings: name -> option name -> expected type.
OPTIONS = {"fix_orientation": bool}
OUTPUT = {"format": str, "quality": int, "background": str, "keep_metadata": bool}
RENAME = {"pattern": str, "counter_start": int}
SECTIONS = {"options": OPTIONS, "output": OUTPUT, "rename": RENAME}


@dataclass
class Preset:
    steps: list[Step]
    fix_orientation: bool = True
    output: OutputSettings = field(default_factory=OutputSettings)
    rename: RenameSettings | None = None


def _load_section(path: Path, section: str, values: object, spec: dict[str, type]) -> dict:
    """Check a section of global settings; returns the values that were given."""
    if not isinstance(values, dict):
        raise PresetError(f"{path}: [{section}] must be a section")
    unknown = sorted(set(values) - set(spec))
    if unknown:
        raise PresetError(
            f"{path}: unknown option(s) {', '.join(unknown)} in [{section}]; "
            f"known options: {', '.join(spec)}"
        )
    for name, value in values.items():
        expected = spec[name]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise PresetError(
                f"{path}: option '{name}' must be {expected.__name__}, "
                f"got {type(value).__name__} ({value!r})"
            )
    return dict(values)


def _changes_files(
    options: dict, output_values: dict, output: OutputSettings, rename: RenameSettings | None
) -> bool:
    """Whether the global settings alone change the files, so that no step is needed.

    Only settings that were written count: ``keep_metadata`` is false by default, and
    ``format = "keep"``, ``keep_metadata = true`` or ``fix_orientation = false`` change nothing.
    """
    return (
        rename is not None
        or output.format != "keep"
        or "quality" in output_values
        or output_values.get("keep_metadata") is False
        or options.get("fix_orientation") is True
    )


def load_preset(path: Path) -> Preset:
    """Read a TOML pipeline preset: the steps in file order and the global sections."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise PresetError(f"preset file not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise PresetError(f"{path}: invalid TOML: {e}") from e

    for section, spec in SECTIONS.items():
        for name in spec:
            if name in data:
                raise PresetError(f"{path}: option '{name}' belongs in the [{section}] section")
    unknown = sorted(set(data) - {"steps", *SECTIONS})
    if unknown:
        raise PresetError(f"{path}: unknown top-level key(s): {', '.join(unknown)}")

    options = _load_section(path, "options", data.get("options", {}), OPTIONS)
    output_values = _load_section(path, "output", data.get("output", {}), OUTPUT)
    try:
        output = OutputSettings(**output_values)
    except ValueError as e:
        raise PresetError(f"{path}: [output]: {e}") from e
    rename = None
    if "rename" in data:
        rename_values = _load_section(path, "rename", data["rename"], RENAME)
        if "pattern" not in rename_values:
            raise PresetError(f"{path}: [rename] needs a 'pattern'")
        try:
            rename = RenameSettings(**rename_values)
        except ValueError as e:
            raise PresetError(f"{path}: [rename]: {e}") from e

    entries = data.get("steps")
    if entries in (None, []) and _changes_files(options, output_values, output, rename):
        entries = []  # renaming, converting etc. alone is a valid run
    elif not isinstance(entries, list) or not entries:
        raise PresetError(f"{path}: define at least one [[steps]] entry")

    steps = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "name" not in entry:
            raise PresetError(f"{path}: [[steps]] #{index} needs a 'name'")
        step_options = {key: value for key, value in entry.items() if key != "name"}
        steps.append(create_step(entry["name"], step_options))
    return Preset(steps=steps, output=output, rename=rename, **options)
