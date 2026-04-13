from __future__ import annotations

import os

from PySide6.QtCore import QTimer  # type: ignore
from PySide6.QtGui import QFont  # type: ignore
from PySide6.QtWidgets import QApplication  # type: ignore

from ..app.bootstrap import default_video_receiver_factory
from ..core.config import load_config
from .components.splash import SplashScreen
from .styles.theme_qss import build_qss
from .views.main_window import MainWindow


def _configure_high_dpi() -> None:
    # Enable High-DPI scaling and crisp pixmaps for 4K monitors.
    # Must run before creating the first QApplication instance.
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

    # Best-effort Qt attributes (safe even if env vars are ignored).
    try:
        from PySide6.QtCore import Qt  # type: ignore
        from PySide6.QtWidgets import QApplication  # type: ignore

        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass


def main() -> None:
    _configure_high_dpi()
    run_qt()


def run_qt() -> None:
    cfg = load_config()
    app = QApplication([])
    app.setStyleSheet(build_qss(theme=cfg.theme, density=cfg.density))
    app.setFont(QFont("Segoe UI", 10))

    splash = SplashScreen()
    splash.show()
    # Center after the window is actually shown (and again shortly after)
    # to avoid transient geometry/cursor issues on some setups.
    QTimer.singleShot(0, splash.center_on_screen)
    QTimer.singleShot(50, splash.center_on_screen)
    app.processEvents()

    def _start() -> None:
        # Keep references alive for the whole app lifetime.
        app._main_window = MainWindow(video_receiver_factory=default_video_receiver_factory())  # type: ignore[attr-defined]
        app._splash = splash  # type: ignore[attr-defined]

        app._main_window.show()  # type: ignore[attr-defined]
        splash.close()

    QTimer.singleShot(0, _start)
    app.exec()


if __name__ == "__main__":
    main()
