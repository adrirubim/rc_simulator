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
    events: queue.Queue = field(default_factory=queue.Queue)
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


def test_video_retry_is_cancelled_by_generation(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("RC_UI_AUTO_SCAN", "0")
    monkeypatch.setenv("RC_UI_DEFAULT_LAYOUT", "A")
    monkeypatch.setenv("RC_UI_START_LAYOUT", "A")

    app = _ensure_qt_app()

    from rc_simulator.ui_qt.views import main_window as mw
    from rc_simulator.ui_qt.views.main_window import MainWindow

    captured = {"cb": None}

    def _fake_single_shot(_ms: int, cb) -> None:
        captured["cb"] = cb

    monkeypatch.setattr(mw.QTimer, "singleShot", _fake_single_shot)

    w = MainWindow(settings=_MemSettings(), controller=_StubController())
    w.show()
    app.processEvents()

    called = {"ok": False}

    def _fake_start_video(_car) -> None:
        called["ok"] = True

    w._start_video_for_car = _fake_start_video  # type: ignore[method-assign]

    w.is_connected = True
    w._schedule_video_retry(5600)  # type: ignore[attr-defined]
    assert captured["cb"] is not None

    # Invalidate pending retries (disconnect/stop video increments generation).
    w._stop_video()  # type: ignore[attr-defined]
    captured["cb"]()
    assert called["ok"] is False
