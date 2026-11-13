#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$DIR/launcher.py" "$@"
fi
echo "Python 3.9 or newer is required. Install Python from python.org, then run this launcher again."
read -r -p "Press Enter to close."
exit 1
