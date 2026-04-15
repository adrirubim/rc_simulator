#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

PY="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found." >&2
    exit 2
  fi
  python3 -m venv "${REPO_ROOT}/.venv"
  PY="${REPO_ROOT}/.venv/bin/python"
fi

# Ensure editable install so `python -m rc_simulator` works with `src/` layout.
"${PY}" -m pip install -U pip >/dev/null 2>&1 || true
"${PY}" -m pip install -e . >/dev/null

exec "${PY}" -m rc_simulator

