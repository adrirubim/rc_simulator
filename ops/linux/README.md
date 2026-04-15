## ops/linux/

Linux/WSL operational scripts.

### What is here

- `run.sh`: runs `python -m rc_simulator` from this repo (creates `.venv/` if missing).
- `install_launcher.sh`: installs a `.desktop` launcher and the SVG icon for the current user.
- `install_service.sh`: installs the systemd unit (headless) using the template in `services/`.
- `camera_receive.sh`: GStreamer helper to preview the UDP H264 video stream.
- `desktop/rc-simulator.desktop`: launcher template (the installer rewrites `Exec=`).
- `services/moza_udp_client.service.in`: systemd unit template (install via `install_service.sh`).

### Recommended usage

- Desktop launcher (no root):

```bash
ops/linux/install.sh --launcher
```

- Full install (launcher + systemd service if systemd is running):

```bash
ops/linux/install.sh --all
```

- Video preview helper:

```bash
ops/linux/camera_receive.sh --port 5600
```

Dry-run (prints actions without making changes):

```bash
ops/linux/install.sh --all --dry-run
```

