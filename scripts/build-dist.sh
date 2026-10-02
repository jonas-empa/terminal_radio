#!/usr/bin/env bash
# Build a standalone terminal-radio binary into dist/.
#
#   ./scripts/build-dist.sh            # uses .venv/bin/pyinstaller
#   PYINSTALLER=pyinstaller ./scripts/build-dist.sh
#
# Produces dist/terminal-radio — a single executable with everything
# bundled except VLC, which must be installed on the target machine
# (sudo apt install vlc).
set -euo pipefail

cd "$(dirname "$0")/.."

PYINSTALLER="${PYINSTALLER:-.venv/bin/pyinstaller}"
if [[ ! -x "$PYINSTALLER" && "$PYINSTALLER" == */* ]]; then
    echo "error: $PYINSTALLER not found — run: .venv/bin/pip install -e '.[dev]'" >&2
    exit 1
fi

mkdir -p build
rm -f build/*.spec

# Absolute paths: with --specpath, relative paths would resolve from the
# spec's directory (build/) instead of the repo root.
ROOT="$(pwd)"

"$PYINSTALLER" \
    --clean \
    --noconfirm \
    --onefile \
    --name terminal-radio \
    --paths "$ROOT/src" \
    --specpath build \
    --add-data "$ROOT/src/terminal_radio/terminal_radio.tcss:terminal_radio" \
    "$ROOT/packaging/entry.py"

echo
echo "Built: $(pwd)/dist/terminal-radio"
echo "Copy it to another Ubuntu machine and run it there; the only"
echo "runtime requirement is VLC: sudo apt install vlc"
