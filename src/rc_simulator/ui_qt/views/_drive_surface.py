from __future__ import annotations

"""
Drive/Dashboard video surface coordinator.

This isolates the non-trivial, regression-prone behavior around:
- moving the shared `video_container` between Dashboard and Drive roots
- enforcing deterministic visibility so the UI cannot become blank

All functions operate on the MainWindow instance passed in (duck-typing) to avoid
import cycles and keep refactors low-risk.
"""


def mount_video_into_drive_root(w) -> None:
    if getattr(w, "drive_root", None) is None:
        return

    # Remove from dashboard layout if still present (best-effort).
    ml = getattr(w, "_mid_layout", None)
    if ml is not None:
        try:
            if ml.indexOf(w.video_container) != -1:
                ml.removeWidget(w.video_container)
        except Exception:
            pass

    # Force parent, then attach to drive root layout.
    try:
        w.video_container.setParent(w.drive_root)
    except Exception:
        pass
    dr_l = w.drive_root.layout()
    if dr_l is not None:
        try:
            if dr_l.indexOf(w.video_container) == -1:
                dr_l.addWidget(w.video_container, 1)
        except Exception:
            pass
    try:
        w.video_container.setVisible(True)
    except Exception:
        pass


def mount_video_into_dashboard(w) -> None:
    if getattr(w, "_mid_layout", None) is None:
        return
    ml = w._mid_layout

    # Remove from drive root if present.
    try:
        dr_l = getattr(w.drive_root, "layout", lambda: None)()
        if dr_l is not None and dr_l.indexOf(w.video_container) != -1:
            dr_l.removeWidget(w.video_container)
    except Exception:
        pass

    # Force parent back to mid panel (even if insert fails, it won't be orphaned).
    try:
        w.video_container.setParent(w.mid_panel)
    except Exception:
        pass

    # Re-insert at original index (best-effort).
    try:
        idx = int(getattr(w, "_video_dashboard_index", -1))
    except Exception:
        idx = -1
    try:
        if idx >= 0:
            ml.insertWidget(idx, w.video_container, 1)
        else:
            ml.addWidget(w.video_container, 1)
    except Exception:
        try:
            ml.addWidget(w.video_container, 1)
        except Exception:
            pass


def ensure_layout_roots_visible(w) -> None:
    """
    Senior safety net: prevent "blank screen" by enforcing a deterministic root.
    """
    try:
        cur = str(getattr(w, "_layout_id", "A") or "A").strip().upper()
    except Exception:
        cur = "A"

    in_drive = cur == "B"
    try:
        if getattr(w, "drive_root", None) is not None:
            w.drive_root.setVisible(bool(in_drive))
    except Exception:
        pass
    try:
        if getattr(w, "_dashboard_center", None) is not None:
            if in_drive:
                w._dashboard_center.hide()
            else:
                w._dashboard_center.show()
    except Exception:
        pass

    # Ensure the video canvas is mounted where it belongs.
    try:
        if in_drive:
            mount_video_into_drive_root(w)
        else:
            mount_video_into_dashboard(w)
    except Exception:
        pass
