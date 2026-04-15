#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

print_usage() {
  cat <<'EOF'
RC Simulator installer (Linux/WSL).

Usage:
  ops/linux/install.sh [--all | --launcher | --service] [--user USER] [--repo PATH] [--dry-run]

Options:
  --all       Install everything available (service + launcher if supported)
  --launcher  Install Linux desktop launcher
  --service   Install systemd service (requires systemd)
  --user      User to run the systemd service as (default: $SUDO_USER or $USER)
  --repo      Repo root path (default: auto-detected)
  --dry-run   Print actions without executing
  -h, --help  Show help
EOF
}

want_all=false
want_launcher=false
want_service=false
dry_run=false
user_name="${SUDO_USER:-${USER:-}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      want_all=true
      shift
      ;;
    --launcher)
      want_launcher=true
      shift
      ;;
    --service)
      want_service=true
      shift
      ;;
    --user)
      user_name="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry_run=true
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

if ! $want_all && ! $want_launcher && ! $want_service; then
  want_all=true
fi
if $want_all; then
  want_launcher=true
  want_service=true
fi

is_wsl=false
if grep -qi microsoft /proc/version 2>/dev/null; then
  is_wsl=true
fi

have_systemd=false
if command -v systemctl >/dev/null 2>&1; then
  # WSL often ships systemctl but without an active systemd PID 1.
  if systemctl is-system-running >/dev/null 2>&1; then
    have_systemd=true
  fi
fi

run() {
  if $dry_run; then
    echo "+ $*"
    return 0
  fi
  "$@"
}

echo "RC Simulator installer"
echo "- repo: ${REPO_ROOT}"
echo "- wsl: ${is_wsl}"
echo "- systemd: ${have_systemd}"

if $want_service; then
  if ! $have_systemd; then
    echo "Skipping systemd service install: systemd is not running on this environment."
    echo "Tip: on WSL you can still use the launcher/run script: ops/linux/run.sh"
  else
    if [[ -z "${user_name}" ]]; then
      echo "Error: --user is required (could not infer from environment)." >&2
      exit 2
    fi
    run bash "${REPO_ROOT}/ops/linux/install_service.sh" --user "${user_name}" --repo "${REPO_ROOT}"
  fi
fi

if $want_launcher; then
  run bash "${REPO_ROOT}/ops/linux/install_launcher.sh"
fi

echo "Done."

