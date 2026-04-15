from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _MemSettings:
    store: dict[str, Any] = field(default_factory=dict)

    def value(self, key: str, defaultValue: Any | None = None) -> Any:
        return self.store.get(key, defaultValue)

    def setValue(self, key: str, value: Any) -> None:
        self.store[key] = value


@dataclass
class _StubController:
    events: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=123))
    scan_thread: Any = None
    drive_thread: Any = None
    stop_event: Any = None

    def start_scan(self) -> bool:  # pragma: no cover
        return False

    def cancel_scan(self) -> bool:  # pragma: no cover
        return False

    def connect(self, _car) -> bool:  # pragma: no cover
        return False

    def disconnect(self) -> None:  # pragma: no cover
        return None

    def shutdown(self) -> None:  # pragma: no cover
        return None


def _ensure_qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_build_diagnostics_text_includes_queue_stats(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("RC_UI_AUTO_SCAN", "0")
    monkeypatch.setenv("RC_UI_DEFAULT_LAYOUT", "A")
    monkeypatch.setenv("RC_UI_START_LAYOUT", "A")

    app = _ensure_qt_app()

    from rc_simulator.ui_qt.views.main_window import MainWindow

    w = MainWindow(settings=_MemSettings(), controller=_StubController())
    w.show()
    app.processEvents()

    txt = w._build_diagnostics_text()  # type: ignore[attr-defined]
    assert "app=rc-simulator" in txt
    assert "qt_platform=" in txt
    assert "events_qsize=" in txt
    assert "events_maxsize=123" in txt
