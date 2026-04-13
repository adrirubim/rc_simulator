from __future__ import annotations

from PySide6.QtCore import QSettings

ORG = "rc-simulator"
APP = "rc-simulator-frontend"


def make_settings() -> QSettings:
    return QSettings(ORG, APP)
