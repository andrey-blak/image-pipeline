"""Build standalone imgpipe executables with PyInstaller.

Usage: python packaging/build.py [onefile|onedir|both]   (default: both)

Output: dist/onefile/imgpipe[.exe] and dist/onedir/imgpipe/imgpipe[.exe].
PyInstaller does not cross-compile: build on the OS you are targeting.
"""

import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
EXCLUDES = ["tkinter", "unittest", "pydoc", "doctest", "test", "pytest"]


def build(mode: str) -> None:
    args = [
        str(ROOT / "packaging" / "entry.py"),
        "--name", "imgpipe",
        "--paths", str(ROOT / "src"),
        "--console",
        "--clean",
        "--noconfirm",
        "--distpath", str(ROOT / "dist" / mode),
        "--workpath", str(ROOT / "build" / mode),
        "--specpath", str(ROOT / "build" / mode),
        f"--{mode}",
    ]
    for module in EXCLUDES:
        args += ["--exclude-module", module]
    if sys.platform != "win32":
        args.append("--strip")
    PyInstaller.__main__.run(args)


def main(argv: list[str]) -> int:
    choice = argv[0] if argv else "both"
    if choice not in ("onefile", "onedir", "both"):
        print(__doc__)
        return 2
    for mode in ("onefile", "onedir") if choice == "both" else (choice,):
        build(mode)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
