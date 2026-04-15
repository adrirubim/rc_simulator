from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlConfig:
    # Input device (MOZA / evdev)
    moza_dev_path: str = "/dev/input/event0"
    allow_no_moza: bool = False

    # Control loop
    control_send_hz: int = 120

    # Calibration / shaping
    steer_gain: float = 2.2
    steer_limit: float = 1.0
    steer_deadzone: float = 0.02
    pedal_deadzone: float = 0.02

    # Inversions
    steer_invert: bool = True
    throttle_invert: bool = False
    brake_invert: bool = False

    @staticmethod
    def from_env() -> ControlConfig:
        """
        Compatibility: reads the existing RC_UI_* env vars (used historically by Qt UI config).

        This keeps services independent from `QtUiConfig` while preserving current operator knobs.
        """
        return ControlConfig(
            moza_dev_path=str(
                os.getenv(
                    "RC_UI_MOZA_DEV_PATH",
                    "/dev/input/by-id/usb-Gudsen_MOZA_R5_Base_290044000C51333033333434-if02-event-joystick",
                )
            ),
            allow_no_moza=str(os.getenv("RC_UI_ALLOW_NO_MOZA", "0") or "0") in ("1", "true", "True"),
            control_send_hz=int(os.getenv("RC_UI_CONTROL_SEND_HZ", "120")),
            steer_gain=float(os.getenv("RC_UI_STEER_GAIN", "2.2")),
            steer_limit=float(os.getenv("RC_UI_STEER_LIMIT", "1.0")),
            steer_deadzone=float(os.getenv("RC_UI_STEER_DEADZONE", "0.02")),
            pedal_deadzone=float(os.getenv("RC_UI_PEDAL_DEADZONE", "0.02")),
            steer_invert=str(os.getenv("RC_UI_STEER_INVERT", "1")) not in ("0", "false", "False"),
            throttle_invert=str(os.getenv("RC_UI_THROTTLE_INVERT", "0")) in ("1", "true", "True"),
            brake_invert=str(os.getenv("RC_UI_BRAKE_INVERT", "0")) in ("1", "true", "True"),
        )
