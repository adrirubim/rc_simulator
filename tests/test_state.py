from __future__ import annotations

from rc_simulator.core.state import AppPhase, StatusPayload, TelemetryPayload


def test_state_enums_and_payloads_smoke() -> None:
    assert AppPhase.IDLE.value == "idle"
    s = StatusPayload(summary="ok", detail="d", phase=AppPhase.CONNECTED)
    assert s.summary == "ok"
    assert s.phase == AppPhase.CONNECTED

    t = TelemetryPayload(steer=0.0, gas=0.1, brake=0.2, output=-0.1, text="x")
    assert t.text == "x"
