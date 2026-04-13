from __future__ import annotations

from collections.abc import Callable

from rc_simulator.ports.video import VideoFrame, VideoReceiver


class _DummyReceiver(VideoReceiver):
    def __init__(self, on_frame: Callable[[VideoFrame], None]) -> None:
        self._on_frame = on_frame

    def start(self) -> bool:
        self._on_frame(VideoFrame(width=1, height=1, rgb_bytes=b"\x00" * 4))
        return True

    def stop(self) -> None:
        return None


def test_video_receiver_contract_smoke() -> None:
    frames: list[VideoFrame] = []
    r = _DummyReceiver(frames.append)
    assert r.start() is True
    assert frames and frames[0].width == 1
    r.stop()
