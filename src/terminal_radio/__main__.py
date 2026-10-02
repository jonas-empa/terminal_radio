"""Command-line entry point for terminal-radio."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="terminal-radio",
        description="Terminal UI internet radio player (Textual + VLC).",
    )
    parser.add_argument(
        "--version", action="version", version=f"terminal-radio {__version__}"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="write debug logs to terminal-radio.log in the config directory",
    )
    args = parser.parse_args(argv)

    if args.debug:
        from .config import CONFIG_DIR

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=CONFIG_DIR / "terminal-radio.log",
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    from .app import TerminalRadioApp

    TerminalRadioApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
