#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LAUNCHER_NAME="rc-simulator.desktop"
SOURCE_LAUNCHER="${SCRIPT_DIR}/desktop/${LAUNCHER_NAME}"
ICON_NAME="rc-simulator"
SOURCE_ICON="${SCRIPT_DIR}/../../assets/icons/${ICON_NAME}.svg"
APPS_DIR="${HOME}/.local/share/applications"
DESKTOP_DIR="${HOME}/Desktop"
ICONS_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

if [[ ! -f "${SOURCE_LAUNCHER}" ]]; then
    echo "Launcher desktop non trovato: ${SOURCE_LAUNCHER}" >&2
    exit 1
fi

if [[ ! -f "${SOURCE_ICON}" ]]; then
    echo "Icon file non trovato: ${SOURCE_ICON}" >&2
    exit 1
fi

mkdir -p "${APPS_DIR}"
sed "s|^Exec=.*$|Exec=${REPO_ROOT}/ops/linux/run.sh|g" "${SOURCE_LAUNCHER}" > "${APPS_DIR}/${LAUNCHER_NAME}"
chmod +x "${APPS_DIR}/${LAUNCHER_NAME}"

mkdir -p "${ICONS_DIR}"
cp "${SOURCE_ICON}" "${ICONS_DIR}/${ICON_NAME}.svg"

if [[ -d "${DESKTOP_DIR}" ]]; then
    sed "s|^Exec=.*$|Exec=${REPO_ROOT}/ops/linux/run.sh|g" "${SOURCE_LAUNCHER}" > "${DESKTOP_DIR}/${LAUNCHER_NAME}"
    chmod +x "${DESKTOP_DIR}/${LAUNCHER_NAME}"
    gio set "${DESKTOP_DIR}/${LAUNCHER_NAME}" metadata::trusted true
fi

update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
gtk-update-icon-cache "${HOME}/.local/share/icons" >/dev/null 2>&1 || true

echo "Launcher installato in ${APPS_DIR}"
if [[ -d "${DESKTOP_DIR}" ]]; then
    echo "Launcher copiato anche su ${DESKTOP_DIR}"
fi