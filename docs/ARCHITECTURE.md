## Architecture (Gold Master 2026)

RC Simulator is organized as a **Ports & Adapters** (Clean Architecture friendly) Python application with explicit infrastructure boundaries, deterministic shutdown, and premium UI polish.

### Entrypoints (unified)

- **UI mode (Qt/PySide6)**: `rc-simulator`
  - Code: `pyproject.toml` → `[project.scripts]` → `rc_simulator/ui_qt/app.py:main`
- **Headless mode (ops/systemd)**: `rc-simulator-headless`
  - Code: `pyproject.toml` → `[project.scripts]` → `rc_simulator/__main_headless__.py:main`
- **Compatibility shim**: `python scripts/moza_udp_client.py`
  - Wrapper that launches UI mode without importing UI modules (no sys.path hacks).

Developer note: `python -m rc_simulator.__main_headless__` remains a supported fallback for ops/systemd,
but the documented “official” commands are the installed entrypoints.

### Layers (Ports & Adapters map)

- **`src/rc_simulator/core/` (brains)**
  - Env-driven configuration (`RC_UI_*`), state enums, events and models (pure types and payloads).
- **`src/rc_simulator/services/` (domain/service logic)**
  - Discovery + control session worker logic. Publishes `UiEvent` objects to a bounded queue.
- **`src/rc_simulator/ports/` (contracts)**
  - Stable interfaces that the app depends on (e.g. video receiver contract).
- **`src/rc_simulator/adapters/` (infrastructure)**
  - Concrete implementations of ports (e.g. GStreamer video receiver).
- **`src/rc_simulator/app/` (coordination)**
  - Owns background threads, stop events, and the UI event queue. Provides deterministic lifecycle operations.
- **`src/rc_simulator/ui_qt/` (presentation)**
  - Qt UI: views/components/styles, premium theme and transitions.

### Video decoupling (port contract)

Video is an optional capability and is modeled as a **port**.

- **Contract**: `src/rc_simulator/ports/video.py`
  - `VideoReceiver` (`start()` / `stop()`)
  - `VideoFrame`: `rgb_bytes` is packed **BGRA (BGRA8888)**
  - `VideoError` with `VideoErrorCode`:
    - `success`
    - `missing_dependencies`
    - `connection_failed`
    - `unknown_error`

- **Adapter (GStreamer, fail-soft)**: `src/rc_simulator/adapters/video_gst.py`
  - Safe to import even if GStreamer GI is missing.
  - On missing dependencies, `start()` returns `False` and reports `VideoErrorCode.MISSING_DEPENDENCIES`.
  - Result: the app remains fully operational without video; the UI can surface a clear, structured error.

### Reliability: deterministic shutdown

`src/rc_simulator/app/session_controller.py` owns scan/drive worker threads and exposes lifecycle methods for UI/headless.

- **Separated stop events**
  - Scan cancellation is isolated from drive sessions (maximum safety and fewer cross-effects).
- **Synchronous deterministic shutdown**
  - `shutdown()` signals both stop events and then `join()`s the threads (best-effort within a timeout budget).
  - Threads are non-daemon to avoid “silent” teardown and ensure predictable close behavior.

### Bounded UI load: backpressure + coalescing

UI responsiveness is protected in two layers:

- **Backpressure at enqueue**: `src/rc_simulator/core/queue_utils.py`
  - If the queue is full and `allow_drop=True`, the new item can be dropped.
  - Otherwise, one **oldest** item is dropped and the enqueue is retried once.
- **Coalescing at drain**: `src/rc_simulator/ui_qt/views/main_window.py`
  - Telemetry bursts are coalesced per UI tick so only the latest payload is rendered, preventing UI lag.

### Premium UX (Obsidian standard)

- **Obsidian base theme**: generated QSS with an obsidian palette (not pure black), defined in `src/rc_simulator/ui_qt/styles/theme_qss.py`.
- **Cinematic fade-to-obsidian**: layout transitions use a fade overlay (`#fadeOverlay`) animated for “cinematic” transitions.
- **Precision HUD**: monospaced telemetry display and robust `◆/◇` status glyphs for stable, zero-jump indicators.

### Ops (OS integration)

See `ops/README.md` and `ops/linux/*` for systemd, launcher, and video helper scripts.

- **Windows one-click**: `install.bat` creates a Desktop shortcut that launches `rc-simulator` inside the repo `.venv` via WSL.
- **systemd**: the unit template runs headless mode (typically `python3 -m rc_simulator.__main_headless__`), which is equivalent to `rc-simulator-headless`.

### Packaging: resource resilience (icons)

The Qt app icon is shipped as package data and loaded via `importlib.resources`:

- Resource path: `rc_simulator/resources/icons/rc-simulator.svg`
- Loader: `src/rc_simulator/ui_qt/app.py` uses `importlib.resources.files(...).joinpath(...)` + `as_file(...)`

This ensures `pip install .` works regardless of repo folder layout (no `../assets/...` path logic).

