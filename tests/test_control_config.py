from __future__ import annotations

from rc_simulator.core.control_config import ControlConfig


def test_control_config_from_env_defaults(monkeypatch) -> None:
    monkeypatch.delenv("RC_UI_CONTROL_SEND_HZ", raising=False)
    cfg = ControlConfig.from_env()
    assert cfg.control_send_hz == 120


def test_control_config_from_env_parses_values(monkeypatch) -> None:
    monkeypatch.setenv("RC_UI_MOZA_DEV_PATH", "/dev/input/event99")
    monkeypatch.setenv("RC_UI_ALLOW_NO_MOZA", "1")
    monkeypatch.setenv("RC_UI_CONTROL_SEND_HZ", "240")
    cfg = ControlConfig.from_env()
    assert cfg.moza_dev_path == "/dev/input/event99"
    assert cfg.allow_no_moza is True
    assert cfg.control_send_hz == 240
