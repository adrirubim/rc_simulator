from __future__ import annotations


def test_session_controller_uses_bounded_queue(monkeypatch) -> None:
    monkeypatch.setenv("RC_EVENT_QUEUE_MAX", "333")
    from rc_simulator.app.session_controller import SessionController

    c = SessionController.create_default()
    assert getattr(c.events, "maxsize", None) == 333
