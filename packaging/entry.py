"""PyInstaller entry point for the standalone terminal-radio binary.

A dedicated entry module (rather than ``__main__.py``) keeps the frozen
bundle independent of how PyInstaller sets ``__name__``.
"""

from __future__ import annotations

import sys

from terminal_radio.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
