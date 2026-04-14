from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UiStrings:
    # Generic
    app_title: str = "RC Simulator"

    # Header / badges
    badge_scanning: str = "SCANNING"
    badge_connecting: str = "CONNECTING"
    badge_disconnecting: str = "DISCONNECTING"
    badge_connected: str = "CONNECTED"
    badge_disconnected: str = "DISCONNECTED"
    badge_video_on: str = "VIDEO ON"
    badge_video_off: str = "VIDEO OFF"
    badge_moza_unknown: str = "MOZA: --"
    badge_moza_wait: str = "MOZA: …"
    badge_moza_ok: str = "MOZA: OK"
    badge_moza_no: str = "MOZA: NO"
    dashboard_button: str = "Dashboard"
    drive_button: str = "Drive"
    drive_tooltip: str = "Enter Drive Mode (layout B)."
    panels_button: str = "Panels"
    panels_tooltip: str = "Open dockable telemetry/trace panels (layout C)."
    dashboard_tooltip: str = "Back to Dashboard (layout A)."

    # Left panel
    search_placeholder: str = "Search cars…"
    list_hint: str = "Tip: run a scan to find cars on the network."
    list_hint_scanning: str = "Scanning for cars…"
    list_hint_found: str = "{count} cars found."
    scan_button: str = "Scan"
    scan_button_scanning: str = "Scanning…"
    scan_button_cancel: str = "Cancel"
    scan_tooltip: str = "Scan the network to find cars."
    connect_button: str = "Connect"
    connect_button_connecting: str = "Connecting…"
    connect_tooltip: str = "Connect to the selected car (Ctrl+Enter)."
    disconnect_button: str = "Disconnect"
    disconnect_tooltip: str = "Disconnect the session (Esc)."

    # Mid panel
    mid_ready: str = "Ready"
    session_status_ready: str = "Session status: Ready"
    session_status_prefix: str = "Session status: "
    session_inactive: str = "Session inactive"
    live_video_label: str = "Live video (embedded in Qt):"
    telemetry_label: str = "Telemetry:"

    # Status / errors / scan
    error_prefix: str = "Error: "
    session_ended: str = "Session ended."
    scan_complete_found: str = "Scan complete: {count} cars found."
    scan_complete_none: str = "Scan complete: no cars found."
    auto_connecting_single: str = "Auto-connecting to {name} ({ip}:{port})…  (Esc or ✕ cancels)"
    active_session_disconnect_first: str = "Active session: disconnect before starting a new scan."
    session_already_active: str = "A session is already active."
    no_cars_found_scan_first: str = "No cars found: run a scan first."
    missing_selection: str = "Missing selection: select a car from the list."
    unable_start_session_active: str = "Unable to start the session (already active)."
    disconnect_requested: str = "Disconnect requested…"
    scan_in_progress_wait_or_cancel: str = "Scan in progress: wait or cancel before connecting."
    shortcuts_help: str = (
        "Shortcuts:  Ctrl+F search  |  Ctrl+Enter connect  |  Ctrl+Shift+F log filter  |  "
        "Ctrl+L clear logs  |  Esc (Drive→Panel / Panel→Disconnect)  |  F1 help"
    )
    layout_changed: str = "Layout: {layout_id}"

    # Bottom hint
    bottom_hint_drive: str = "Ctrl+F search | Ctrl+L clear logs | Esc to exit Drive Mode"
    bottom_hint_connected: str = "Ctrl+F search | Ctrl+L clear logs | Esc to disconnect"
    bottom_hint_idle: str = "Ctrl+F search | Ctrl+L clear logs | F11 fullscreen (if supported)"

    # Drive mode safety (frameless fullscreen escape hatch)
    drive_mode_hint: str = (
        "Drive Mode: Esc exits | F11 toggles fullscreen (if supported) | Ctrl+Shift+Esc emergency exit"
    )

    # Drive guard (connect-first)
    drive_guard_title: str = "Active connection required"
    drive_guard_body: str = "Connect to a car first, then enter Drive Mode."

    # Video
    video_not_available: str = "Video: not available"
    video_connecting: str = "Video: connecting…"
    video_requirements_button: str = "Video requirements"
    video_requirements_tooltip: str = "Show what to install for embedded video."
    overlay_disconnect_button: str = "DISCONNECT"
    overlay_disconnect_tooltip: str = "Disconnect now (Esc)."
    overlay_title_video: str = "Video"
    overlay_connecting: str = "Connecting…"
    overlay_waiting_connection: str = "Waiting for connection…"
    overlay_no_active_session: str = "No active session."
    overlay_video_not_available: str = "Video not available"
    overlay_missing_deps: str = "Missing GI/GStreamer dependencies for embedded video."
    overlay_no_frames: str = "No frames received. Check network/port or retry."
    overlay_retry: str = "Retry"
    video_backend_not_configured: str = "Video: backend not configured."
    video_backend_not_available: str = "Video: backend not available (GI/GStreamer)."
    video_deps_hint: str = (
        "For embedded video install: sudo apt install -y python3-gi gstreamer1.0-plugins-base gstreamer1.0-plugins-good"
    )

    # Log dock
    log_dock_title: str = "System log"
    log_filter_placeholder: str = "Filter logs…"
    log_pause: str = "Pause"
    log_resume: str = "Resume"
    log_pause_tooltip: str = "Pause log auto-scroll (also auto-enables when you scroll up)."
    log_clear: str = "Clear"
    log_clear_tooltip: str = "Clear the log view."

    # Exit / shutdown
    exit_confirm_title: str = "Exit RC Simulator?"
    exit_confirm_body: str = (
        "A session is active or an operation is in progress.\n\nDo you want to disconnect/stop and exit now?"
    )
    exit_confirm_body_idle: str = "Exit the application now?"
    exit_confirm_exit: str = "Exit"
    exit_confirm_cancel: str = "Cancel"


UI = UiStrings()
