from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ...core.config import load_config


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

    conn = QLabel("DISCONNESSO", hud)
    moza = QLabel("MOZA: --", hud)
    video = QLabel("VIDEO OFF", hud)
    output = QLabel("+0.000", hud)
    for b in (conn, moza, video, output):
        b.setProperty("badge", True)
        b.setProperty("badgeKind", "muted")
        layout.addWidget(b)

    hud.setVisible(False)
    return Hud(widget=hud, conn=conn, moza=moza, video=video, output=output)
