#!/usr/bin/env bash
# run-godot.sh -- launch Godot inside the dev container.
#
# Usage (inside container):
#   run-godot.sh                         # headless (CI/export mode)
#   run-godot.sh --editor                # editor via X11 forwarding
#   run-godot.sh --xvfb                  # editor on virtual framebuffer
#   run-godot.sh --export "Linux/X11" out.zip
#
# Requirements:
#   - DISPLAY must be set for --editor mode (X11 forwarding from host).
#   - xvfb-run is available when --xvfb is requested.
#   - godot-editor binary must exist for --editor / --xvfb (build with GODOT_EDITOR=1).

set -euo pipefail

HEADLESS_BIN="/usr/local/bin/godot"
EDITOR_BIN="/usr/local/bin/godot-editor"

MODE="headless"

# Parse our wrapper flags; pass everything else through to Godot.
PASS_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --editor)
            MODE="editor"
            shift
            ;;
        --xvfb)
            MODE="xvfb"
            shift
            ;;
        --export)
            # --export is a Godot flag; pass it through with headless binary.
            PASS_ARGS+=("--headless" "--export" "$2")
            shift 2
            ;;
        *)
            PASS_ARGS+=("$1")
            shift
            ;;
    esac
done

case "$MODE" in
    headless)
        exec "$HEADLESS_BIN" --headless "${PASS_ARGS[@]+"${PASS_ARGS[@]}"}"
        ;;
    editor)
        if [[ ! -x "$EDITOR_BIN" ]]; then
            echo "ERROR: Godot editor binary not found at $EDITOR_BIN"
            echo "Rebuild the image with:  docker build --build-arg GODOT_EDITOR=1 -t lotr-dev build/docker/"
            exit 1
        fi
        if [[ -z "${DISPLAY:-}" ]]; then
            echo "ERROR: DISPLAY is not set. Enable X11 forwarding (e.g. -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix)"
            exit 1
        fi
        exec "$EDITOR_BIN" "${PASS_ARGS[@]+"${PASS_ARGS[@]}"}"
        ;;
    xvfb)
        if [[ ! -x "$EDITOR_BIN" ]]; then
            echo "ERROR: Godot editor binary not found at $EDITOR_BIN"
            echo "Rebuild the image with:  docker build --build-arg GODOT_EDITOR=1 -t lotr-dev build/docker/"
            exit 1
        fi
        exec xvfb-run -a "$EDITOR_BIN" "${PASS_ARGS[@]+"${PASS_ARGS[@]}"}"
        ;;
esac
