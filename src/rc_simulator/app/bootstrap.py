from __future__ import annotations

from ..adapters.video_gst import GstVideoReceiver
from ..ports.video import VideoReceiverFactory


def default_video_receiver_factory() -> VideoReceiverFactory:
    # Composition root: app layer is allowed to choose adapters.
    return GstVideoReceiver
