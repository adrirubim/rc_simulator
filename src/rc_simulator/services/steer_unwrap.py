from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SteerUnwrapper:
    steer_min: int
    steer_max: int
    wrap_jump_frac: float = 0.45

    last_raw: int | None = None
    unwrap_offset: int = 0

    @property
    def steer_range(self) -> int:
        return max(1, int(self.steer_max) - int(self.steer_min))

    @property
    def wrap_jump(self) -> int:
        return int(self.steer_range * float(self.wrap_jump_frac))

    def update(self, raw_value: int) -> int:
        val = int(raw_value)

        if self.last_raw is not None:
            delta = val - int(self.last_raw)
            if abs(delta) > self.wrap_jump:
                # Wheel passed through the wrap boundary.
                if delta > 0:
                    self.unwrap_offset -= self.steer_range
                else:
                    self.unwrap_offset += self.steer_range

        self.last_raw = val

        val_unwrapped = val + int(self.unwrap_offset)
        # Wrap back into [steer_min, steer_max) equivalent range.
        return int(((val_unwrapped - self.steer_min) % self.steer_range) + self.steer_min)
