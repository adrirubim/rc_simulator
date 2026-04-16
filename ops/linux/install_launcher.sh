#!/usr/bin/env bash
set -euo pipefail

print_usage() {
    cat <<'EOF'
Install the RC Simulator desktop launcher (current user).

Usage:
  ops/linux/install_launcher.sh [--dry-run]

Options:
  --dry-run   Print actions without executing
  -h, --help  Show help
EOF
}

dry_run=false

while [[ $# -gt 0 ]]; do
    case "$1" in
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

run() {
    if $dry_run; then
        echo "+ $*"
        return 0
    fi
    "$@"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LAUNCHER_NAME="rc-simulator.desktop"
SOURCE_LAUNCHER="${SCRIPT_DIR}/desktop/${LAUNCHER_NAME}"
ICON_NAME="rc-simulator"
SOURCE_ICON="${REPO_ROOT}/src/rc_simulator/resources/icons/${ICON_NAME}.svg"
APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
if [[ -z "${DESKTOP_DIR}" ]]; then
    DESKTOP_DIR="${HOME}/Desktop"
fi
ICONS_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

if [[ ! -f "${SOURCE_LAUNCHER}" ]]; then
    echo "Desktop launcher not found: ${SOURCE_LAUNCHER}" >&2
    exit 1
fi

if [[ ! -f "${SOURCE_ICON}" ]]; then
    echo "Icon file not found: ${SOURCE_ICON}" >&2
    exit 1
fi

run mkdir -p "${APPS_DIR}"
sed "s|^Exec=.*$|Exec=${REPO_ROOT}/ops/linux/run.sh|g" "${SOURCE_LAUNCHER}" > "${APPS_DIR}/${LAUNCHER_NAME}"
run chmod 0644 "${APPS_DIR}/${LAUNCHER_NAME}"

run mkdir -p "${ICONS_DIR}"
run cp "${SOURCE_ICON}" "${ICONS_DIR}/${ICON_NAME}.svg"

if [[ -d "${DESKTOP_DIR}" ]]; then
    sed "s|^Exec=.*$|Exec=${REPO_ROOT}/ops/linux/run.sh|g" "${SOURCE_LAUNCHER}" > "${DESKTOP_DIR}/${LAUNCHER_NAME}"
    # Some desktop environments require .desktop entries on the Desktop to be executable.
    run chmod 0755 "${DESKTOP_DIR}/${LAUNCHER_NAME}"
    if ! $dry_run; then
        gio set "${DESKTOP_DIR}/${LAUNCHER_NAME}" metadata::trusted true >/dev/null 2>&1 || true
    else
        echo "+ gio set \"${DESKTOP_DIR}/${LAUNCHER_NAME}\" metadata::trusted true"
    fi
fi

if ! $dry_run; then
    update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
    gtk-update-icon-cache "${HOME}/.local/share/icons" >/dev/null 2>&1 || true
else
    echo "+ update-desktop-database \"${APPS_DIR}\""
    echo "+ gtk-update-icon-cache \"${HOME}/.local/share/icons\""
fi

echo "Launcher installed to ${APPS_DIR}"
if [[ -d "${DESKTOP_DIR}" ]]; then
    echo "Launcher also copied to ${DESKTOP_DIR}"
fi