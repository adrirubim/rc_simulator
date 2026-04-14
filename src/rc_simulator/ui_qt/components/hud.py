from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ...core.config import load_config
from ..strings import UI

MOZA_OK_GLYPH = "◆"  # robust on 4K vs typographic dot
MOZA_NO_GLYPH = "◇"
MOZA_UNKNOWN_STATE = "--"
MOZA_WAIT_STATE = ".."


def format_moza_badge(*, state: str) -> str:
    """
    MOZA badge text with constant glyph + fixed-width state token.
    States are 2 chars to prevent horizontal "jumping" in HUD/header.
    """
    s = (state or "").strip().upper()
    if s in ("OK",):
        glyph = MOZA_OK_GLYPH
        token = "OK"
    elif s in ("NO", "OFF", "DISCONNECTED", "FALSE"):
        glyph = MOZA_NO_GLYPH
        token = "NO"
    elif s in ("WAIT", "CONNECTING", "...", "…"):
        glyph = MOZA_NO_GLYPH
        token = MOZA_WAIT_STATE
    else:
        glyph = MOZA_NO_GLYPH
        token = MOZA_UNKNOWN_STATE
    return f"{glyph} MOZA: {token}"


@dataclass(frozen=True)
class Hud:
    widget: QWidget
    conn: QLabel
    moza: QLabel
    video: QLabel
    output: QLabel


def build_hud(*, parent: QWidget) -> Hud:
    cfg = load_config()
    hud = QWidget(parent)
    layout = QHBoxLayout(hud)
    if cfg.density == "compact":
        layout.setContentsMargins(8, 8, 8, 8)
    else:
        layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    conn = QLabel(UI.badge_disconnected, hud)
    moza = QLabel(UI.badge_moza_unknown, hud)
    video = QLabel(UI.badge_video_off, hud)
    output = QLabel("+0.000", hud)
    for b in (conn, moza, video, output):
        b.setProperty("badge", True)
        b.setProperty("badgeKind", "muted")
        layout.addWidget(b)
    output.setProperty("mono", True)

    hud.setVisible(False)
    return Hud(widget=hud, conn=conn, moza=moza, video=video, output=output)
