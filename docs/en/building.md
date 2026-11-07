# Building standalone executables

imgpipe can be packaged as a single executable that needs no Python and no installation. The tool is [PyInstaller](https://pyinstaller.org); it cannot cross-compile, so each executable is built on the OS it targets.

## Local build

```
uv sync --group build
uv run python packaging/build.py onefile
```

Result: `dist/onefile/imgpipe` (Linux) or `dist/onefile/imgpipe.exe` (Windows). `build.py onedir` makes a folder instead (`dist/onedir/imgpipe/`): it starts about 0.15 s faster but must be shipped as a whole folder. `build.py both` builds both.

## Releases (Linux and Windows)

`.github/workflows/build.yml` builds both executables on GitHub runners, runs the tests and the executable smoke test, and uploads the files as artifacts. Start it from the Actions tab (*Run workflow*), or push a tag such as `v0.1.0`: the tag also creates a GitHub release with the executables and `preset.toml` (the example preset, which the executables read by default).

## Notes

- The Linux binary runs on systems with the same or a newer glibc than the build machine; CI builds on Ubuntu 22.04 for that reason.
- A onefile executable unpacks itself to a temporary folder on every start.
- Unsigned Windows executables may trigger a SmartScreen or antivirus warning.
