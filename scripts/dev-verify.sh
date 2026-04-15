#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -U pip
if [[ -f "requirements-dev.lock" ]]; then
  # Reproducible dev environment: constrain transitive dependencies.
  python -m pip install -c requirements-dev.lock -e ".[dev]"
else
  python -m pip install -e ".[dev]"
fi

rm -rf src/*.egg-info src/**/*.egg-info 2>/dev/null || true

python3 scripts/audit_layout.py

ruff format --check .
ruff check .

pytest -q

