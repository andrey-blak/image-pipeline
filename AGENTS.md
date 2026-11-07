# AGENTS.md

## Layout
- `src/imgpipe/` – Python package (src layout): `cli.py`, `config.py` (TOML -> steps), `pipeline.py` (runner), `imageio.py` (find/load/save), `steps/` (one module per step plus the registry in `steps/__init__.py`)
- `tests/` – tests; test images are generated in `tmp_path`, none are committed
- `config.example.toml` – commented example config
- `docs/en/` – English documentation (other languages later, e.g. `docs/ru/`)
- `.venv/` – virtual environment (gitignored)
- `.tools/` – standalone tools such as `uv` (gitignored)
- `input/`, `output/` – image folders

## Commands
- Install/sync: `uv sync`
- Tests: `uv run pytest`
- Run: `uv run python -m imgpipe --config config.example.toml --seed 1`

## Conventions
- Everything the project needs stays inside the project.
- Ask before creating anything outside the project folder; clean up temporary files afterwards.
- Pipeline config is TOML, separate from `pyproject.toml` (project metadata only). No config given: the tool does nothing.
- EXIF orientation fix always runs first. Output (format, quality) and naming are config sections, not pipeline steps.
- A new step = one module in `src/imgpipe/steps/` (a dataclass registered with `@register("name")`, its fields are the config options) + an import line in `steps/__init__.py` + tests + a section in `docs/en/config.md`.
- Steps that use random values are named with an `rnd_` prefix (e.g. `rnd_saturation`); deterministic steps have no prefix.
- All new functionality is covered by automated tests.
- Originals are never modified.
- Do not commit `input/` or `output/` unless explicitly told to.
