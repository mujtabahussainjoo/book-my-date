#!/bin/bash
set -eu
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$DIR/uninstaller/uninstall.py" --all --purge --yes --force "$@"
fi
if command -v python >/dev/null 2>&1; then
    exec python "$DIR/uninstaller/uninstall.py" --all --purge --yes --force "$@"
fi
echo "Python 3.9 or newer is required. Install Python 3 from python.org, then run this file again." >&2
exit 1
