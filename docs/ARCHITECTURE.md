## Architecture (high level)

### Entrypoint

- `python -m rc_simulator` → `src/rc_simulator/__main__.py`

### Main packages

- `src/rc_simulator/ui_qt/`
  - Qt UI (PySide6): windows, components and styles.
- `src/rc_simulator/app/`
  - Bootstrap and session control (high-level coordination).
- `src/rc_simulator/services/`
  - Discovery and control (service logic consumed by the UI).
- `src/rc_simulator/core/`
  - Configuration, state, events and models (types/payloads).
- `src/rc_simulator/ports/` y `src/rc_simulator/adapters/`
  - Ports and adapters (for example, video).

### Typical flow

1. Startup → bootstrap/config
2. Qt UI initializes
3. “Car” discovery (UDP / network)
4. Control session (MOZA/evdev → UDP to the car)
5. Optional video (GStreamer), depending on environment

### Ops (OS integration)

See `ops/README.md` and `ops/linux/*` for systemd, launcher and video scripts.

