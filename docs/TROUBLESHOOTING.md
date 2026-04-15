## Troubleshooting

### UI doesn't show up (WSLg)

- Ensure you're on WSLg (Windows 11) and that `DISPLAY` is set:

```bash
echo "$DISPLAY"
```

- If `DISPLAY` is empty, try a simple GUI app (for example `xclock` if available) to validate the GUI stack.

### Windows shortcut does not start the app

Use the dedicated shortcut installer:

- `ops/windows/install_shortcut.cmd`

If launching fails, check the runner log:

- `%TEMP%\rc_simulator_run.log`
- `%USERPROFILE%\Desktop\rc_simulator_run.log`

### `Permission denied` when running `.venv/bin/python`

This usually happens after **moving the project** and the venv still points to old paths.

Fix (recreate the venv in the current directory):

```bash
cd /var/www/rc_simulator
deactivate 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

### `evdev` can't see MOZA / no access to `/dev/input`

- On WSL/Windows: device passthrough may not be available.
- On Linux, check permissions/groups for `/dev/input` (for example the `input` group).

### Video doesn't work (GStreamer)

Install dependencies (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y python3-gi gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
```

### Security artifacts (pip-audit / SBOM)

GitHub Actions generates dependency security artifacts on each run of the Security workflow:

- `pip-audit.json`: Python dependency vulnerability report
- `sbom.cdx.json`: CycloneDX SBOM for the installed environment

Test the script:

```bash
ops/linux/camera_receive.sh 5600 0
```

### File explorer shows `*.Zone.Identifier`

On Windows, when browsing `\\wsl.localhost\...`, the explorer may show **Alternate Data Streams (ADS)** like `:Zone.Identifier`.
They are not "real files" on Linux and do not affect execution in WSL.

