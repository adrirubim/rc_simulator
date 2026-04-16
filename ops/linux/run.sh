#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ ! -f "${REPO_ROOT}/scripts/bootstrap_venv.sh" ]]; then
  echo "Error: missing bootstrap script: ${REPO_ROOT}/scripts/bootstrap_venv.sh" >&2
  exit 2
fi

bash "${REPO_ROOT}/scripts/bootstrap_venv.sh" --quiet

exec "${REPO_ROOT}/.venv/bin/rc-simulator"

