#!/usr/bin/env bash
set -euo pipefail

print_usage() {
  cat <<'EOF'
Bootstrap (create/update) the local .venv and install the package editable.

Usage:
  scripts/bootstrap_venv.sh [--extras EXTRAS] [--constraint FILE] [--quiet]

Examples:
  scripts/bootstrap_venv.sh
  scripts/bootstrap_venv.sh --extras dev
  scripts/bootstrap_venv.sh --extras "[dev]"
  scripts/bootstrap_venv.sh --extras ".[dev]" --constraint requirements-dev.lock
EOF
}

extras=""
constraint=""
quiet=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --extras)
      extras="${2:-}"
      shift 2
      ;;
    --constraint|--constraints|-c)
      constraint="${2:-}"
      shift 2
      ;;
    --quiet|-q)
      quiet=true
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found." >&2
  exit 2
fi

if $quiet; then
  log() { :; }
else
  log() { echo "$@"; }
fi

log "Setting up environment..."

if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv .venv
fi

PY=".venv/bin/python"

"${PY}" -m pip install -U pip >/dev/null 2>&1 || true

install_spec="-e"
if [[ -z "${extras}" ]]; then
  pkg_spec="."
elif [[ "${extras}" == .* ]]; then
  pkg_spec="${extras}"
elif [[ "${extras}" == \[*\] ]]; then
  pkg_spec=".${extras}"
else
  pkg_spec=".[${extras}]"
fi

pip_args=()
if [[ -n "${constraint}" ]]; then
  pip_args+=("-c" "${constraint}")
fi

if $quiet; then
  "${PY}" -m pip install "${pip_args[@]}" ${install_spec} "${pkg_spec}" >/dev/null
else
  "${PY}" -m pip install "${pip_args[@]}" ${install_spec} "${pkg_spec}"
fi

log "Setting up environment... Done."

