from __future__ import annotations

from ..adapters.qt_settings import make_qt_settings
from ..adapters.video_gst import GstVideoReceiver
from ..core.settings import SettingsStore
from ..ports.video import VideoReceiverFactory
from .session_controller import SessionController


def default_video_receiver_factory() -> VideoReceiverFactory:
    # Composition root: app layer is allowed to choose adapters.
    return GstVideoReceiver


def default_settings() -> SettingsStore:
    return make_qt_settings()


def default_controller() -> SessionController:
    return SessionController.create_default()
