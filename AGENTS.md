# AGENTS.md

## Layout
- `src/imgpipe/` – Python package (src layout): `cli.py`, `preset.py` (TOML -> steps), `pipeline.py` (runner), `imageio.py` (find/load, EXIF orientation, metadata), `output.py` (the `[output]` section: format, quality, background, metadata, writing files), `naming.py` (the `[rename]` section: file name patterns), `colors.py` (color parsing shared by steps), `rotation.py` (rotation shared by `rotate` and `rnd_rotate`), `steps/` (one module per step plus the registry in `steps/__init__.py`)
- `packaging/` – PyInstaller entry point, build and benchmark scripts; `.github/workflows/build.yml` builds the Linux and Windows executables
- `tests/` – tests; test images are generated in `tmp_path`, none are committed
- `preset.example.toml` – commented example preset
- `docs/en/` – English documentation (other languages later, e.g. `docs/ru/`)
- `.venv/` – virtual environment (gitignored)
- `.tools/` – standalone tools such as `uv` (gitignored)
- `input/`, `output/` – image folders

## Commands
- Install/sync: `uv sync`
- Tests: `uv run pytest`
- Run: `uv run python -m imgpipe --preset preset.example.toml --seed 1`

## Conventions
- Everything the project needs stays inside the project.
- Ask before creating anything outside the project folder; clean up temporary files afterwards.
- Pipeline preset is TOML, separate from `pyproject.toml` (project metadata only). No preset given: the tool does nothing.
- EXIF orientation is applied first, before the steps, when `exif_orientation` is `"apply"` (the default; `"keep"` and `"remove"` leave the pixels alone; `"remove"` drops the tag, `"keep"` writes it even when the rest of metadata is stripped). It is not a step: it lives in `imageio.py` (`load`, `fix_orientation`, `EXIF_ORIENTATION_MODES`) and is applied by `Pipeline.run`; the option is set in the preset's `[options]` section. With `"keep"` the pixels stay as stored, so a step that depends on direction or on width/height must use `ctx.mirrored` / `ctx.swaps_axes` to work on the photo as it is shown (see `rotate`, `resize`). Global settings live in `[options]` (a section, so it may appear anywhere in the file; bare top-level keys after a `[[steps]]` would belong to that step); add new ones to `OPTIONS` in `preset.py`. Output (format, quality, background, metadata) is the `[output]` section and naming is the `[rename]` one (`naming.py`): they are preset sections, applied after the last step, not pipeline steps (`output.py`; a new format = one entry in `FORMATS`).
- A new step = one module in `src/imgpipe/steps/` (a dataclass registered with `@register("name")`, its fields are the preset options) + an import line in `steps/__init__.py` + tests + a section in `docs/en/preset.md`.
- Steps that use random values are named with an `rnd_` prefix (e.g. `rnd_saturation`); deterministic steps have no prefix.
- A step reports what it applied for `--verbose` with `ctx.record(key, text)` (e.g. `saturation`, `+4.2%`). Size changes are measured by the pipeline, so steps do not record them.
- Dry run (`-n`): a step declares `depends_on_pixels` (including the image mode) and `depends_on_size` — what its own result (size produced, values recorded) needs from the incoming image; both default to True. The pipeline sets `ctx.skip_pixels` / `ctx.skip_resize` for a step when no later step depends on pixels / size. A step may use them to skip work (a skipped size change reports the size via `ctx.record_size`), but must still draw its random values and `ctx.record(...)` its changes, so a dry run reports exactly what a real run would. Add a test that the dry-run report equals the real one.
- All new functionality is covered by automated tests.
- Originals are never modified.
- Do not commit `input/` or `output/` unless explicitly told to.
