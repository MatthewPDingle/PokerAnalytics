#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
VENV_DIR=${VENV_DIR:-.venv}

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in $VENV_DIR" >&2
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Activate the environment
if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
else
  # shellcheck disable=SC1090
  source "$VENV_DIR/Scripts/activate"
fi

pip install --upgrade pip
pip install -e ".[dev]"

echo "Environment ready. Activate with: source $VENV_DIR/bin/activate" >&2
