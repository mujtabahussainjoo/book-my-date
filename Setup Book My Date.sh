#!/bin/sh
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$DIR/launcher.py" --setup "$@"
fi
if command -v python >/dev/null 2>&1; then
    exec python "$DIR/launcher.py" --setup "$@"
fi
printf '%s\n' "Python 3.9 or newer is required. Install Python, then run this launcher again."
printf '%s\n' "Press Enter to close."
read -r _
exit 1
