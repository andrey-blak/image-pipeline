# AGENTS.md

## Layout
- `src/imgpipe/` – Python package (src layout): `cli.py`, `config.py` (TOML -> steps), `pipeline.py` (runner), `imageio.py` (find/load/save), `colors.py` (color parsing shared by steps), `steps/` (one module per step plus the registry in `steps/__init__.py`)
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
- EXIF orientation fix always runs first. It is not a step: it lives in `imageio.py` (`load`, `fix_orientation`) and is applied by `Pipeline.run`; the option `fix_orientation` (default true) in the config's `[options]` table switches it off. Global settings live in `[options]` (a table, so it may appear anywhere in the file; bare top-level keys after a `[[steps]]` would belong to that step); add new ones to `OPTIONS` in `config.py`. Output (format, quality) and naming are config sections, not pipeline steps.
- A new step = one module in `src/imgpipe/steps/` (a dataclass registered with `@register("name")`, its fields are the config options) + an import line in `steps/__init__.py` + tests + a section in `docs/en/config.md`.
- Steps that use random values are named with an `rnd_` prefix (e.g. `rnd_saturation`); deterministic steps have no prefix.
- A step reports what it applied for `--verbose` with `ctx.record(key, text)` (e.g. `saturation`, `+4.2%`). Size changes are measured by the pipeline, so steps do not record them.
- Dry run (`-n`): a step declares `depends_on_pixels` (including the image mode) and `depends_on_size` — what its own result (size produced, values recorded) needs from the incoming image; both default to True. The pipeline sets `ctx.skip_pixels` / `ctx.skip_resize` for a step when no later step depends on pixels / size. A step may use them to skip work (a skipped size change reports the size via `ctx.record_size`), but must still draw its random values and `ctx.record(...)` its changes, so a dry run reports exactly what a real run would. Add a test that the dry-run report equals the real one.
- All new functionality is covered by automated tests.
- Originals are never modified.
- Do not commit `input/` or `output/` unless explicitly told to.
