#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

constraint_args=()
if [[ -f "requirements-dev.lock" ]]; then
  # Reproducible dev environment: constrain transitive dependencies.
  constraint_args=(--constraint "requirements-dev.lock")
fi

bash scripts/bootstrap_venv.sh --extras dev "${constraint_args[@]}"

# shellcheck disable=SC1091
source .venv/bin/activate

rm -rf src/*.egg-info src/**/*.egg-info 2>/dev/null || true

python3 scripts/audit_layout.py

ruff format --check .
ruff check .

pytest -q

