## ops/

Scripts and assets for deployment / OS integration.

### `ops/linux/`

- `install_service.sh`: installs the systemd unit in `services/`.
- `services/moza_udp_client.service`: systemd unit file (source of truth).
- `camera_receive.sh`: GStreamer-based video receiver helper.
- `install_launcher.sh`: installs a `.desktop` launcher (expects `ops/linux/desktop/rc-simulator.desktop`).

### `ops/windows/`

- `install_shortcut.ps1`: creates a Windows Desktop shortcut that launches the app via WSL.
- `uninstall_shortcut.ps1`: removes the shortcut.
- `install_shortcut.cmd`: double-click installer (wraps the `.ps1`).
- `uninstall_shortcut.cmd`: double-click uninstaller (wraps the `.ps1`).

