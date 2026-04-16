from __future__ import annotations

import os
import sys
from importlib import resources as importlib_resources
from pathlib import Path

from PySide6.QtCore import QTimer  # type: ignore
from PySide6.QtGui import QFont, QIcon  # type: ignore
from PySide6.QtWidgets import QApplication  # type: ignore

from rc_simulator.app.bootstrap import default_controller, default_settings, default_video_receiver_factory
from rc_simulator.core.config import load_config
from rc_simulator.resources import icons as icons_pkg
from rc_simulator.ui_qt.components.splash import SplashScreen
from rc_simulator.ui_qt.styles.theme_qss import build_qss
from rc_simulator.ui_qt.views.main_window import MainWindow


def _configure_windows_appusermodel_id() -> None:
    # Ensures the taskbar icon/grouping uses our AppUserModelID on Windows.
    # Without this, Windows may show a generic/system icon in some launch scenarios.
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("rc-simulator")  # type: ignore[attr-defined]
    except Exception:
        pass


def _frozen_meipass_path(*parts: str) -> Path | None:
    """
    When running from a PyInstaller bundle, access extracted data files via sys._MEIPASS.

    We keep this tiny and defensive because it must not interfere with normal execution.
    """
    if not getattr(sys, "frozen", False):
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    try:
        p = Path(meipass, *parts)
        return p if p.exists() else None
    except Exception:
        return None


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
    _configure_windows_appusermodel_id()
    app = QApplication([])
    # On Linux/Wayland the taskbar icon can be resolved via the .desktop entry.
    # Tie this process/window to our desktop file name when available.
    try:
        app.setDesktopFileName("rc-simulator")
    except Exception:
        pass
    app.setStyleSheet(build_qss(theme=cfg.theme, density=cfg.density))
    # Let QSS own font sizing; set only a best-effort family fallback.
    app.setFont(QFont("Segoe UI"))

    # Window/taskbar icon: load from packaged resources for portability.
    icon = _load_app_icon()
    if icon is not None:
        try:
            app.setWindowIcon(icon)
        except Exception:
            pass

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
        try:
            if "icon" in locals() and icon is not None:
                w.setWindowIcon(icon)
        except Exception:
            pass
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


def _load_app_icon() -> QIcon | None:
    try:
        frozen = _frozen_meipass_path("rc_simulator", "resources", "icons", "rc-simulator.svg")
        if frozen is not None:
            icon = QIcon(str(frozen))
            if not icon.isNull():
                return icon

        icon_ref = importlib_resources.files(icons_pkg).joinpath("rc-simulator.svg")
        with importlib_resources.as_file(icon_ref) as p:
            if p.exists():
                icon = QIcon(str(p))
                if not icon.isNull():
                    return icon
    except Exception:
        return None
    return None


if __name__ == "__main__":
    main()
