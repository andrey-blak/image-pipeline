"""Launcher used by PyInstaller as the executable's entry point."""

import sys

from imgpipe.cli import main

sys.exit(main())
