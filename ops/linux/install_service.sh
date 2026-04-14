#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="moza_udp_client.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEMPLATE_PATH="${REPO_ROOT}/ops/linux/services/moza_udp_client.service.in"
TARGET_PATH="/etc/systemd/system/${SERVICE_NAME}"

print_usage() {
  cat <<'EOF'
Install RC Simulator systemd service (Linux).

Usage:
  ops/linux/install_service.sh [--user USER] [--repo PATH] [--display VALUE] [--xauthority PATH] [--python PATH]

Options:
  --user        Linux user to run the service as (default: $SUDO_USER or $USER)
  --repo        Repository root path (default: auto-detected)
  --display     DISPLAY value (default: :0)
  --xauthority  XAUTHORITY path (default: %h/.Xauthority)
  --python      Python executable (default: /usr/bin/python3)
  -h, --help    Show this help
EOF
}

USER_NAME="${SUDO_USER:-${USER:-}}"
DISPLAY_VALUE=":0"
XAUTHORITY_VALUE="%h/.Xauthority"
PYTHON_PATH="/usr/bin/python3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      USER_NAME="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --display)
      DISPLAY_VALUE="${2:-}"
      shift 2
      ;;
    --xauthority)
      XAUTHORITY_VALUE="${2:-}"
      shift 2
      ;;
    --python)
      PYTHON_PATH="${2:-}"
      shift 2
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

if [[ -z "${USER_NAME}" ]]; then
  echo "Error: --user is required (could not infer from environment)." >&2
  exit 2
fi

TEMPLATE_PATH="${REPO_ROOT}/ops/linux/services/moza_udp_client.service.in"
if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Error: template not found: ${TEMPLATE_PATH}" >&2
  exit 2
fi

echo "Installing ${SERVICE_NAME}..."
echo "- repo: ${REPO_ROOT}"
echo "- user: ${USER_NAME}"
echo "- display: ${DISPLAY_VALUE}"
echo "- xauthority: ${XAUTHORITY_VALUE}"
echo "- python: ${PYTHON_PATH}"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

sed \
  -e "s|@USER@|${USER_NAME}|g" \
  -e "s|@DISPLAY@|${DISPLAY_VALUE}|g" \
  -e "s|@XAUTHORITY@|${XAUTHORITY_VALUE}|g" \
  -e "s|@PYTHON@|${PYTHON_PATH}|g" \
  "${TEMPLATE_PATH}" > "${tmp}"

sudo cp "${tmp}" "${TARGET_PATH}"
sudo chmod 0644 "${TARGET_PATH}"

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "Installed and restarted: ${SERVICE_NAME}"