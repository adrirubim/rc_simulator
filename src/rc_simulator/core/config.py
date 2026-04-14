from __future__ import annotations

import os
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class QtUiConfig:
    default_layout: str = os.getenv("RC_UI_DEFAULT_LAYOUT", "A")  # A|B|C
    start_layout: str = os.getenv("RC_UI_START_LAYOUT", "B")  # A|B|C
    theme: str = os.getenv("RC_UI_THEME", "slate")  # slate|glass
    density: str = os.getenv("RC_UI_DENSITY", "normal")  # normal|compact
    queue_poll_ms: int = int(os.getenv("RC_UI_QUEUE_POLL_MS", "75"))
    max_events_per_tick: int = int(os.getenv("RC_UI_MAX_EVENTS_PER_TICK", "200"))
    video_target_fps: int = int(os.getenv("RC_UI_VIDEO_FPS", "30"))
    video_latency_ms: int = int(os.getenv("RC_UI_VIDEO_LATENCY_MS", "120"))
    log_max_lines: int = int(os.getenv("RC_UI_LOG_MAX_LINES", "2000"))
    auto_scan: bool = os.getenv("RC_UI_AUTO_SCAN", "1") in ("1", "true", "True")
    auto_connect_single: bool = os.getenv("RC_UI_AUTO_CONNECT_SINGLE", "1") in ("1", "true", "True")
    auto_connect_delay_ms: int = int(os.getenv("RC_UI_AUTO_CONNECT_DELAY_MS", "1200"))

    # Control session (MOZA / evdev)
    moza_dev_path: str = os.getenv(
        "RC_UI_MOZA_DEV_PATH",
        "/dev/input/by-id/usb-Gudsen_MOZA_R5_Base_290044000C51333033333434-if02-event-joystick",
    )
    allow_no_moza: bool = os.getenv("RC_UI_ALLOW_NO_MOZA", "0") in ("1", "true", "True")
    control_send_hz: int = int(os.getenv("RC_UI_CONTROL_SEND_HZ", "120"))
    steer_gain: float = float(os.getenv("RC_UI_STEER_GAIN", "2.2"))
    steer_limit: float = float(os.getenv("RC_UI_STEER_LIMIT", "1.0"))
    steer_deadzone: float = float(os.getenv("RC_UI_STEER_DEADZONE", "0.02"))
    pedal_deadzone: float = float(os.getenv("RC_UI_PEDAL_DEADZONE", "0.02"))

    steer_invert: bool = os.getenv("RC_UI_STEER_INVERT", "1") not in ("0", "false", "False")
    throttle_invert: bool = os.getenv("RC_UI_THROTTLE_INVERT", "0") in ("1", "true", "True")
    brake_invert: bool = os.getenv("RC_UI_BRAKE_INVERT", "0") in ("1", "true", "True")


def load_config() -> QtUiConfig:
    cfg = QtUiConfig()
    # IMPORTANT: some options may be overridden at runtime (e.g. headless flags) via env vars.
    # QtUiConfig defaults are evaluated at import time, so refresh selected env-driven fields here.
    cfg = replace(
        cfg,
        moza_dev_path=os.getenv("RC_UI_MOZA_DEV_PATH", cfg.moza_dev_path),
        allow_no_moza=os.getenv("RC_UI_ALLOW_NO_MOZA", "0") in ("1", "true", "True"),
        start_layout=os.getenv("RC_UI_START_LAYOUT", cfg.start_layout),
        auto_scan=os.getenv("RC_UI_AUTO_SCAN", "1") in ("1", "true", "True"),
        auto_connect_single=os.getenv("RC_UI_AUTO_CONNECT_SINGLE", "1") in ("1", "true", "True"),
        auto_connect_delay_ms=int(os.getenv("RC_UI_AUTO_CONNECT_DELAY_MS", str(cfg.auto_connect_delay_ms))),
    )
    if cfg.default_layout not in ("A", "B", "C"):
        return QtUiConfig(default_layout="A")
    if cfg.theme not in ("slate", "glass"):
        return QtUiConfig(default_layout=cfg.default_layout, theme="slate")
    if cfg.density not in ("normal", "compact"):
        return QtUiConfig(default_layout=cfg.default_layout, theme=cfg.theme, density="normal")
    return cfg
