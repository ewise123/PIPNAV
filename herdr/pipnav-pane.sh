#!/bin/sh
# Run PipNav inside a herdr pane.
#
# herdr sets HERDR_PLUGIN_ROOT to this repo when it launches the plugin, so the
# project virtualenv is found without hardcoding anyone's home directory.
set -e

root="${HERDR_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

if [ -x "$root/.venv/bin/pipnav" ]; then
    exec "$root/.venv/bin/pipnav"
fi
exec pipnav
