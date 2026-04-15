from __future__ import annotations

import os

from PySide6.QtCore import QTimer  # type: ignore
from PySide6.QtGui import QFont  # type: ignore
from PySide6.QtWidgets import QApplication  # type: ignore

from ..app.bootstrap import default_controller, default_settings, default_video_receiver_factory
from ..core.config import load_config
from .components.splash import SplashScreen
from .styles.theme_qss import build_qss
from .views.main_window import MainWindow


def _configure_high_dpi() -> None:
    # Enable High-DPI scaling and crisp pixmaps for 4K monitors.
    # Must run before creating the first QApplication instance.
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")


def _configure_qpa_platform() -> None:
    """
    WSLg/Wayland has known fragility with certain window-state transitions (0x0 configure).
    Prefer the XCB backend (XWayland) ONLY when explicitly requested, since it may require
    additional system packages (e.g. libxcb-cursor0).
    """
    # Respect explicit user choice (or our explicit override flag).
    if os.environ.get("QT_QPA_PLATFORM"):
        return
    if os.environ.get("RC_UI_FORCE_QPA_XCB") == "1":
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def main() -> None:
    _configure_high_dpi()
    _configure_qpa_platform()
    _run_qt()


def _run_qt() -> None:
    cfg = load_config()
    app = QApplication([])
    app.setStyleSheet(build_qss(theme=cfg.theme, density=cfg.density))
    # Let QSS own font sizing; set only a best-effort family fallback.
    app.setFont(QFont("Segoe UI"))

    splash = SplashScreen()
    splash.show()
    # Center after the window is actually shown (and again shortly after)
    # to avoid transient geometry/cursor issues on some setups.
    QTimer.singleShot(0, splash.center_on_screen)
    QTimer.singleShot(50, splash.center_on_screen)
    app.processEvents()

    def _start() -> None:
        # Keep references alive for the whole app lifetime.
        app._main_window = MainWindow(  # type: ignore[attr-defined]
            video_receiver_factory=default_video_receiver_factory(),
            settings=default_settings(),
            controller=default_controller(),
        )
        app._splash = splash  # type: ignore[attr-defined]

        w = app._main_window  # type: ignore[attr-defined]
        w.show()
        # Reveal: animate internal content only (platform-safe).
        try:
            w.start_reveal(ms=300)
        except Exception:
            pass

        # Keep splash on top for the first half of the reveal.
        QTimer.singleShot(150, splash.close)

    QTimer.singleShot(0, _start)
    app.exec()


if __name__ == "__main__":
    main()
