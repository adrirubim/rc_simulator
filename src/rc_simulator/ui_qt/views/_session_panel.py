from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton

from ...core.state import AppPhase
from ..strings import UI


@dataclass(slots=True, weakref_slot=True)
class SessionPanel:
    settings: object
    controller: object
    btn_drive: QPushButton
    btn_scan: QPushButton
    btn_connect: QPushButton
    btn_disconnect: QPushButton
    btn_overlay_disconnect: QPushButton
    hud: object
    phase_progress: QProgressBar
    mid_state: object
    mid_state_title: QLabel
    mid_state_body: QLabel
    bottom: QLabel
    get_is_fullscreen: Callable[[], bool]
    refresh_video_overlay: Callable[[], None]

    def _set_button_kind(self, btn: QPushButton, kind: str) -> None:
        """
        Set button variant via objectName (used by QSS selectors).

        kind: "primary" | "secondary" | "danger" | "base"
        """
        want = {
            "primary": "primaryButton",
            "secondary": "secondaryButton",
            "danger": "dangerButton",
            "base": "",
        }.get(str(kind), "")
        if btn.objectName() == want:
            return
        btn.setObjectName(want)
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def update_bottom_hint(self, *, is_connected: bool) -> None:
        # Keep hints consistent with Esc logic and current layout.
        # Drive may be fullscreen (X11) or windowed (Wayland).
        if self.btn_drive.isChecked():
            self.bottom.setText(UI.bottom_hint_drive)
            return
        if is_connected:
            self.bottom.setText(UI.bottom_hint_connected)
            return
        self.bottom.setText(UI.bottom_hint_idle)

    def update_controls(
        self,
        *,
        cars_present: bool,
        has_selection: bool,
        is_connecting: bool,
        is_scanning: bool,
        is_connected: bool,
        filtered_indices_len: int,
        selected_index: int | None,
    ) -> None:
        has_sel = selected_index is not None and 0 <= int(selected_index) < int(filtered_indices_len)
        # "session_active" must reflect actual activity, not the mere existence of stop_event.
        # stop_event may be created for scans and can persist after completion.
        drive_thread = getattr(self.controller, "drive_thread", None)
        scan_thread = getattr(self.controller, "scan_thread", None)
        drive_alive = bool(drive_thread is not None and getattr(drive_thread, "is_alive", lambda: False)())
        scan_alive = bool(scan_thread is not None and getattr(scan_thread, "is_alive", lambda: False)())
        # "busy" means we should not offer new actions (connect/scan), but we still
        # want Scan visible while scanning to reflect the "Scanning…" state.
        busy = bool(drive_alive or scan_alive or is_connecting)
        scanning = bool(is_scanning)

        # Minimal UI: Disconnect only when actually connected.
        show_disconnect = bool(is_connected)
        # Only show Connect once we have scan results AND a valid selection.
        show_connect = bool((not busy) and (not scanning) and (not is_connected) and cars_present and has_sel)
        # Show Scan while scanning (to reflect "Scanning…"), and when there are no cars yet.
        show_scan = bool((not is_connected) and (scanning or ((not busy) and (not cars_present))))

        self.btn_disconnect.setVisible(show_disconnect)
        self.btn_connect.setVisible(show_connect)
        self.btn_scan.setVisible(show_scan)

        self.btn_disconnect.setEnabled(bool(is_connected))
        self.btn_connect.setEnabled(bool(cars_present and has_sel and (not is_connecting) and (not is_scanning)))
        # While scanning, Scan acts as Cancel (must stay enabled).
        self.btn_scan.setEnabled(bool(scanning or ((not busy) and (not scanning))))

        # Button kinds: reflect state (stable, operator-friendly).
        # - Connected: Disconnect is primary action (danger).
        # - Scanning: Scan becomes primary (shows "Scanning…").
        # - Idle: Connect is primary when available; Scan is secondary.
        if show_disconnect:
            self._set_button_kind(self.btn_disconnect, "danger")
        if show_connect:
            self._set_button_kind(self.btn_connect, "primary")
        if show_scan:
            self._set_button_kind(self.btn_scan, "primary" if is_scanning else "secondary")

        # Make state visible in the primary actions (real-time operator UX).
        self.btn_scan.setText(UI.scan_button_cancel if scanning else UI.scan_button)
        self.btn_connect.setText(UI.connect_button_connecting if is_connecting else UI.connect_button)
        self.btn_disconnect.setText(UI.disconnect_button)

        # Keep layout stable: don't toggle visibility (it shifts the video block).
        # Instead, switch between "busy" indeterminate and "idle" empty state.
        busy_progress = bool(is_scanning or is_connecting)
        try:
            if self.phase_progress.property("busy") != busy_progress:
                self.phase_progress.setProperty("busy", busy_progress)
                self.phase_progress.style().unpolish(self.phase_progress)
                self.phase_progress.style().polish(self.phase_progress)
            if busy_progress:
                # Indeterminate.
                self.phase_progress.setRange(0, 0)
            else:
                # Empty but visible.
                self.phase_progress.setRange(0, 1)
                self.phase_progress.setValue(0)
        except Exception:
            pass
        self.refresh_video_overlay()

    def refresh_mid_state(
        self,
        *,
        is_scanning: bool,
        is_connecting: bool,
        is_connected: bool,
        cars_present: bool,
        has_selection: bool,
    ) -> None:
        # Middle panel should focus on video/telemetry.
        # Only show a mid-state card for transient busy states (scan/connect),
        # not for empty/idle selection guidance (which lives in the left panel).
        if is_scanning:
            # Avoid duplicate scan messaging: scanning is already shown via header badge,
            # left hint, and a toast. Keep the center focused on the video overlay.
            self.mid_state.setVisible(False)
            return

        if is_connecting:
            self.mid_state_title.setText(UI.mid_state_connecting_title)
            self.mid_state_body.setText(UI.mid_state_connecting_body)
            self.mid_state.setVisible(True)
            return

        # Otherwise, keep it hidden (idle/connected UI should be clean).
        self.mid_state.setVisible(False)

    def derive_flags_from_phase(
        self,
        *,
        phase: AppPhase,
        was_connected: bool,
    ) -> tuple[bool, bool, bool, bool]:
        is_scanning = bool(phase == AppPhase.SCANNING)
        is_connecting = bool(phase == AppPhase.CONNECTING)
        should_set_connected = bool(phase == AppPhase.CONNECTED and (not was_connected))
        should_set_disconnected = bool(phase in (AppPhase.IDLE, AppPhase.ERROR) and was_connected)
        return is_scanning, is_connecting, should_set_connected, should_set_disconnected
