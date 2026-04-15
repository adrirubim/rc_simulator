## ops/

Scripts and assets for deployment / OS integration.

### Release / support checklist (Linux-first)

- Run CI parity gate: `./scripts/dev-verify.sh`
- Capture support bundle:
  - In-app: Settings -> "Copy diagnostics"
  - Attach `pip-audit.json` and `sbom.cdx.json` from CI artifacts when available

### One-command install

- Linux/WSL: `ops/linux/install.sh --all` (installs launcher; installs systemd service if systemd is running)
- Windows: `ops/windows/install_shortcut.cmd` (recommended; creates a Desktop shortcut that launches via WSL with logs on failure)

### "Double click" install

- Windows (recommended): double-click `ops/windows/install_shortcut.cmd`
- Linux: make it executable once (`chmod +x ops/linux/install.sh`), then double-click `ops/linux/install.sh` and choose "Run"
- Note (Windows Explorer): if file extensions are hidden, make sure you're running `install_shortcut.cmd` (not the `.ps1`).

### `ops/linux/`

- `install_service.sh`: installs the systemd unit into `/etc/systemd/system/`.
- `services/moza_udp_client.service.in`: systemd unit **template** (source of truth).
  - Install via `ops/linux/install_service.sh --user <username>`.
  - The unit runs headless (`python3 -m rc_simulator.__main_headless__`) and assumes `rc-simulator` is installed for that user/machine.
- `camera_receive.sh`: GStreamer-based video receiver helper.
- `install_launcher.sh`: installs a `.desktop` launcher (expects `ops/linux/desktop/rc-simulator.desktop`).

### `ops/windows/`

- `install_shortcut.ps1`: creates a Windows Desktop shortcut that launches the app via WSL.
- `run_rc_simulator.cmd`: runner used by the shortcut; captures logs to `%TEMP%\rc_simulator_run.log` and mirrors to the Desktop on failure.
- `uninstall_shortcut.ps1`: removes the shortcut.
- `install_shortcut.cmd`: double-click installer (wraps the `.ps1`).
- `uninstall_shortcut.cmd`: double-click uninstaller (wraps the `.ps1`).

