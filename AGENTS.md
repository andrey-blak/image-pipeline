# AGENTS.md

## Layout
- `src/imgpipe/` – Python package (src layout)
- `tests/` – tests, sample images
- `docs/en/` – English documentation (other languages later, e.g. `docs/ru/`)
- `.venv/` – virtual environment (gitignored)
- `.tools/` – standalone tools such as `uv` (gitignored)
- `input/`, `output/` – image folders

## Commands
- Python: `.venv/bin/python`
- `uv` and `pytest` commands: added after the uv step.

## Conventions
- Everything the project needs stays inside the project.
- Ask before creating anything outside the project folder; clean up temporary files afterwards.
- Pipeline config is TOML, separate from `pyproject.toml` (project metadata only). No config given: the tool does nothing.
- EXIF orientation fix always runs first. Output (format, quality) and naming are config sections, not pipeline steps.
- Originals are never modified. 
- Do not commit `input/` or `output/` unless explicitly told to.
