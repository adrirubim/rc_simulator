from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UiStrings:
    # Generic
    app_title: str = "RC Simulator"

    # Header / badges
    badge_scanning: str = "SCANNING"
    badge_connected: str = "CONNECTED"
    badge_disconnected: str = "DISCONNECTED"
    badge_video_off: str = "VIDEO OFF"
    drive_button: str = "Drive"
    drive_tooltip: str = "Drive Mode (fullscreen). Press Esc to exit Drive Mode."
    debug_tooltip: str = "Dockable telemetry/trace panels (layout C)."

    # Left panel
    search_placeholder: str = "Search cars…"
    list_hint: str = "Tip: run a scan to find cars on the network."
    scan_button: str = "Scan"
    scan_tooltip: str = "Scan the network to find cars."
    connect_button: str = "Connect"
    connect_tooltip: str = "Connect to the selected car (Ctrl+Enter)."
    disconnect_button: str = "Disconnect"
    disconnect_tooltip: str = "Disconnect the session (Esc)."

    # Mid panel
    mid_ready: str = "Ready"
    session_status_ready: str = "Session status: Ready"
    session_inactive: str = "Session inactive"
    live_video_label: str = "Live video (embedded in Qt):"
    telemetry_label: str = "Telemetry:"

    # Video
    video_not_available: str = "Video: not available"
    video_connecting: str = "Video: connecting…"
    video_requirements_button: str = "Video requirements"
    video_requirements_tooltip: str = "Show what to install for embedded video."
    overlay_disconnect_button: str = "DISCONNECT"
    overlay_disconnect_tooltip: str = "Disconnect now (Esc)."

    # Log dock
    log_dock_title: str = "System log"
    log_filter_placeholder: str = "Filter logs…"
    log_pause: str = "Pause"
    log_resume: str = "Resume"
    log_pause_tooltip: str = "Pause log auto-scroll (also auto-enables when you scroll up)."
    log_clear: str = "Clear"
    log_clear_tooltip: str = "Clear the log view."


UI = UiStrings()
