from __future__ import annotations

from rc_simulator.services.steer_unwrap import SteerUnwrapper


def test_unwrap_no_wrap() -> None:
    u = SteerUnwrapper(steer_min=0, steer_max=100, wrap_jump_frac=0.45)
    assert u.update(10) == 10
    assert u.update(20) == 20
    assert u.update(30) == 30


def test_unwrap_wrap_forward_then_backward() -> None:
    # Range 0..100, wrap_jump=45 -> delta > 45 triggers wrap.
    u = SteerUnwrapper(steer_min=0, steer_max=100, wrap_jump_frac=0.45)

    assert u.update(90) == 90
    # Cross wrap boundary (forward wrap): 90 -> 5 (delta=-85)
    assert u.update(5) == 5
    # Go back across boundary: 5 -> 95 (delta=90)
    assert u.update(95) == 95
