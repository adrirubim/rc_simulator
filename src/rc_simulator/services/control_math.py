from __future__ import annotations


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def norm_axis(value: int, amin: int, amax: int, *, invert: bool = False) -> float:
    if amax == amin:
        return 0.0
    x = (value - amin) / (amax - amin)
    x = x * 2.0 - 1.0
    if invert:
        x = -x
    return clamp(x, -1.0, 1.0)


def norm_trigger(value: int, amin: int, amax: int, *, invert: bool = False) -> float:
    if amax == amin:
        return 0.0
    x = (value - amin) / (amax - amin)
    if invert:
        x = 1.0 - x
    return clamp(x, 0.0, 1.0)


def apply_deadzone(x: float, dz: float) -> float:
    return 0.0 if abs(x) < dz else x
