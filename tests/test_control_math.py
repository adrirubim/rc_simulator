from __future__ import annotations

from rc_simulator.services.control_math import apply_deadzone, clamp, norm_axis, norm_trigger


def test_clamp() -> None:
    assert clamp(-2.0, -1.0, 1.0) == -1.0
    assert clamp(0.5, -1.0, 1.0) == 0.5
    assert clamp(2.0, -1.0, 1.0) == 1.0


def test_norm_axis_basic() -> None:
    assert norm_axis(0, 0, 100) == -1.0
    assert norm_axis(50, 0, 100) == 0.0
    assert norm_axis(100, 0, 100) == 1.0
    assert norm_axis(0, 0, 100, invert=True) == 1.0


def test_norm_trigger_basic() -> None:
    assert norm_trigger(0, 0, 100) == 0.0
    assert norm_trigger(50, 0, 100) == 0.5
    assert norm_trigger(100, 0, 100) == 1.0
    assert norm_trigger(0, 0, 100, invert=True) == 1.0


def test_deadzone() -> None:
    assert apply_deadzone(0.01, 0.02) == 0.0
    assert apply_deadzone(-0.01, 0.02) == 0.0
    assert apply_deadzone(0.03, 0.02) == 0.03
