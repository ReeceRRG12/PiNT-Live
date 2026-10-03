#!/bin/sh
# Native macOS build. Install the application and PyInstaller first.
set -eu
cd "$(dirname "$0")"
if [ "$#" -ne 1 ]; then
    echo "Usage: sh build.sh v0.7.0-beta.3" >&2
    exit 2
fi
exec python3 scripts/build_release.py --tag "$1"
