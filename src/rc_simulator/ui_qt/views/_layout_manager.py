"""
Layout/transitions coordinator extracted from MainWindow.

Design goal:
- Keep MainWindow as an orchestrator (signals/state), not a 3k+ LOC layout machine.
- Preserve behavior exactly; no UI/logic changes should be introduced here.

This module intentionally operates on the MainWindow instance passed in (duck-typing),
to avoid circular imports and keep refactors low-risk.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer  # type: ignore

from ...core.state import AppPhase
from ..strings import UI


def apply_layout(w, layout_id: str) -> None:
    if getattr(w, "settings", None) is None:
        return

    # No-op if already in the requested layout.
    try:
        want = str(layout_id or "").strip().upper()
        if want not in ("A", "B", "C", "D"):
            want = "A"
        cur = str(getattr(w, "_layout_id", "") or "").strip().upper()
        if cur and cur == want:
            return
    except Exception:
        pass

    # Avoid re-entrant transitions.
    if bool(getattr(w, "_layout_transition_in_progress", False)):
        w._layout_transition_queued = layout_id
        return

    # Never animate transitions into/out of Drive.
    try:
        want = str(layout_id or "").strip().upper()
        if want not in ("A", "B", "C", "D"):
            want = "A"
        cur = str(getattr(w, "_layout_id", "") or "").strip().upper()
        if cur == "B" or want == "B":
            apply_layout_now(w, layout_id)
            return
    except Exception:
        pass

    # Tests/CI: offscreen platform.
    try:
        import os

        if str(os.environ.get("QT_QPA_PLATFORM", "") or "") == "offscreen":
            apply_layout_now(w, layout_id)
            return
    except Exception:
        pass

    # Not visible yet: apply immediately.
    try:
        if not bool(w.isVisible()):
            apply_layout_now(w, layout_id)
            return
    except Exception:
        pass

    # Safety: avoid animation while connecting/disconnecting.
    try:
        if bool(getattr(w, "is_connecting", False)) or bool(getattr(w, "phase", None) == AppPhase.DISCONNECTING):
            apply_layout_now(w, layout_id)
            return
    except Exception:
        pass

    w._layout_transition_in_progress = True
    w._layout_transition_current = layout_id
    w._layout_transition_queued = None

    # Watchdog: never allow fade overlay to get stuck.
    try:
        QTimer.singleShot(1400, lambda: force_end_layout_transition_if_stuck(w))
    except Exception:
        pass

    def _after_fade_out() -> None:
        try:
            apply_layout_now(w, layout_id)
        finally:
            try:
                QTimer.singleShot(
                    0,
                    lambda: w._fade_overlay_to(0.0, ms=200, on_done=lambda: on_layout_fade_in_done(w)),
                )
            except Exception:
                on_layout_fade_in_done(w)

    w._fade_overlay_to(1.0, ms=200, on_done=_after_fade_out)


def force_end_layout_transition_if_stuck(w) -> None:
    try:
        if not bool(getattr(w, "_layout_transition_in_progress", False)):
            return
    except Exception:
        return
    try:
        w._layout_transition_in_progress = False
    except Exception:
        pass
    try:
        w._set_fade_overlay_alpha(0.0)
        if getattr(w, "_fade_overlay", None) is not None:
            w._fade_overlay.hide()
    except Exception:
        pass


def on_layout_fade_in_done(w) -> None:
    w._layout_transition_in_progress = False
    current = getattr(w, "_layout_transition_current", None)
    queued = getattr(w, "_layout_transition_queued", None)
    w._layout_transition_current = None
    w._layout_transition_queued = None
    if queued is not None and queued != current:
        apply_layout(w, queued)


def apply_layout_now(w, layout_id: str) -> None:
    apply_layout_now_impl(w, layout_id)


def apply_layout_now_impl(w, layout_id: str) -> None:
    """
    Extracted from MainWindow._apply_layout_now (copy/move).
    """
    if getattr(w, "settings", None) is None:
        return
    w.setUpdatesEnabled(False)
    try:
        layout_id = layout_id if layout_id in ("A", "B", "C", "D") else "A"
        w._layout_id = layout_id
        w.settings.setValue("layout_id", layout_id)
        if layout_id == "B":
            w._pre_drive_was_maximized = bool(w.isMaximized())
            w.btn_drive.setChecked(True)
            w.btn_debug.setChecked(False)
            w.btn_settings.setChecked(False)
            w._sync_header_nav_buttons(layout_id)

            if getattr(w, "drive_root", None) is not None:
                w.drive_root.setVisible(True)
            if getattr(w, "_dashboard_center", None) is not None:
                w._dashboard_center.hide()

            w._mount_video_into_drive_root()

            w.header_widget.hide()
            w.banner.hide()
            w.left_panel.hide()
            w.bottom.hide()
            w.telemetry_dock.hide()
            w.trace_dock.hide()
            try:
                rl = getattr(w, "_root_layout", None)
                if rl is not None:
                    rl.setContentsMargins(0, 0, 0, 0)
                    rl.setSpacing(0)
            except Exception:
                pass

            try:
                w.settings_panel.setVisible(False)
                w.video_container.setVisible(True)
            except Exception:
                pass
            w.hud.setVisible(True)
            w.hud_output.setVisible(False)
            w.btn_overlay_disconnect.setVisible(bool(getattr(w, "is_connected", False)))
            w.drive_guard_overlay.setVisible(not bool(getattr(w, "is_connected", False)))
            try:
                w.live_video_label.setVisible(False)
                w.telemetry_caption.setVisible(False)
                w.telemetry_label.setVisible(False)
            except Exception:
                pass
            try:
                w.session_label.setVisible(False)
                w.detail_label.setVisible(False)
                w.phase_progress.setVisible(False)
            except Exception:
                pass
            try:
                if not bool(getattr(w, "is_connected", False)):
                    w.video_view.setVisible(False)
                    w.video_overlay.setVisible(False)
                else:
                    w.video_view.setVisible(True)
            except Exception:
                pass
            try:
                w.drive_guard_action.setVisible(not bool(getattr(w, "is_connected", False)))
            except Exception:
                pass
            try:
                w._apply_drive_guard_state()
            except Exception:
                pass
            w.drive_banner.setVisible(False)
            try:
                w.drive_guard_overlay.raise_()
                w.hud.raise_()
                w.btn_overlay_disconnect.raise_()
                w.drive_banner.raise_()
            except Exception:
                pass

            w._run_when_window_has_size(w.showFullScreen)
            if w._is_wayland():
                try:
                    QTimer.singleShot(
                        220,
                        lambda: None if w.isFullScreen() else w._run_when_window_has_size(w.showMaximized),
                    )
                except Exception:
                    pass
            w._show_banner("muted", UI.drive_mode_hint, auto_hide_ms=0)
            w._update_bottom_hint()
        else:
            if getattr(w, "drive_root", None) is not None:
                w.drive_root.setVisible(False)
            if getattr(w, "_dashboard_center", None) is not None:
                w._dashboard_center.show()

            w._mount_video_into_dashboard()

            try:
                rl = getattr(w, "_root_layout", None)
                if rl is not None:
                    if w.cfg.density == "compact":
                        rl.setContentsMargins(10, 10, 10, 10)
                        rl.setSpacing(8)
                    else:
                        rl.setContentsMargins(12, 12, 12, 12)
                        rl.setSpacing(10)
            except Exception:
                pass
            try:
                w.session_label.setVisible(True)
                w.detail_label.setVisible(True)
                w.phase_progress.setVisible(True)
            except Exception:
                pass
            try:
                if w._is_wayland():
                    w._run_when_window_has_size(w.showNormal)
                else:
                    if bool(getattr(w, "_pre_drive_was_maximized", False)):
                        w._run_when_window_has_size(w.showMaximized)
                    else:
                        w._run_when_window_has_size(w.showNormal)
            except Exception:
                pass
            w.btn_drive.setChecked(False)
            w.btn_overlay_disconnect.setVisible(False)
            w.hud.setVisible(False)
            w.drive_banner.setVisible(False)
            w.drive_guard_overlay.setVisible(False)
            w.hud_output.setVisible(True)
            try:
                w.live_video_label.setVisible(False)
                w.telemetry_caption.setVisible(True)
                w.telemetry_label.setVisible(True)
            except Exception:
                pass
            try:
                w.video_view.setVisible(True)
                w._refresh_video_overlay()
            except Exception:
                pass
            try:
                w.drive_guard_action.setVisible(True)
            except Exception:
                pass

            w.header_widget.show()
            w.banner.setVisible(bool(w.banner_text.text().strip()))
            if layout_id == "C":
                w.left_panel.hide()
            else:
                w.left_panel.show()
            w.bottom.show()
            if layout_id == "C":
                w.telemetry_dock.show()
                w.trace_dock.show()
                w.btn_debug.setChecked(True)
                w.btn_settings.setChecked(False)
                try:
                    w.log_dock.hide()
                except Exception:
                    pass
                try:
                    w.settings_panel.setVisible(False)
                    w.video_container.setVisible(True)
                    w.telemetry_caption.setVisible(False)
                    w.telemetry_label.setVisible(False)
                    w.live_video_label.setVisible(False)
                except Exception:
                    pass
            elif layout_id == "D":
                w.btn_debug.setChecked(False)
                w.btn_settings.setChecked(True)
                w.telemetry_dock.hide()
                w.trace_dock.hide()
                try:
                    w.log_dock.hide()
                except Exception:
                    pass
                w.left_panel.hide()
                try:
                    w.settings_panel.setVisible(True)
                    w.video_container.setVisible(False)
                    w.telemetry_caption.setVisible(False)
                    w.telemetry_label.setVisible(False)
                    w.live_video_label.setVisible(False)
                except Exception:
                    pass
            else:
                w.btn_debug.setChecked(False)
                w.btn_settings.setChecked(False)
                w.telemetry_dock.hide()
                w.trace_dock.hide()
                try:
                    w.log_dock.show()
                except Exception:
                    pass
                try:
                    w.settings_panel.setVisible(False)
                    w.video_container.setVisible(True)
                    w.live_video_label.setVisible(False)
                    w.telemetry_caption.setVisible(True)
                    w.telemetry_label.setVisible(True)
                except Exception:
                    pass
            w._sync_header_nav_buttons(layout_id)
            w._update_bottom_hint()
    finally:
        w.setUpdatesEnabled(True)
        try:
            if not bool(getattr(w, "_layout_transition_in_progress", False)):
                w._set_fade_overlay_alpha(0.0)
                if getattr(w, "_fade_overlay", None) is not None:
                    w._fade_overlay.hide()
        except Exception:
            pass
        try:
            w._ensure_layout_roots_visible()
        except Exception:
            pass
