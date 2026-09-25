#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PY="$ROOT_DIR/.venv/bin/python"

if [ -f "$VENV_PY" ]; then
    exec "$VENV_PY" "$ROOT_DIR/Python/main.py" --tray "$@"
else
    exec python3 "$ROOT_DIR/Python/main.py" --tray "$@"
fi
