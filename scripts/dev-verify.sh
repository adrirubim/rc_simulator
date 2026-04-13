#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -U pip
python -m pip install -e ".[dev]"

python3 scripts/audit_layout.py

ruff format --check .
ruff check .

pytest -q

