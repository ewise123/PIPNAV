#!/bin/sh
# Open (or focus) the PipNav pane. Wired to a herdr action so it is reachable
# from herdr's UI rather than only from the command line.
set -e
herdr_bin="${HERDR_BIN_PATH:-herdr}"
exec "$herdr_bin" plugin pane open \
    --plugin pipnav.launcher \
    --entrypoint browser \
    --placement tab \
    --focus
