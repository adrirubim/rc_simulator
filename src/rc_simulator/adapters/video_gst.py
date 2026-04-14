from __future__ import annotations

import threading
from collections.abc import Callable

from ..ports.video import VideoFrame, VideoReceiver


class GstVideoReceiver(VideoReceiver):
    """
    Best-effort embedded video receiver.

    - If GStreamer GI isn't available, start() returns False and reports via on_error.
    - This adapter is intentionally minimal; it is safe to import even without GI.
    """

    def __init__(
        self,
        *,
        port: int,
        latency_ms: int,
        on_frame: Callable[[VideoFrame], None],
        on_error: Callable[[str], None],
    ):
        self.port = int(port)
        self.latency_ms = int(latency_ms)
        self.on_frame = on_frame
        self.on_error = on_error

        self._running = False
        self._pipeline = None
        self._bus = None
        self._bus_thread: threading.Thread | None = None
        self._stop_bus = threading.Event()

    def start(self) -> bool:
        try:
            import gi  # type: ignore

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst  # type: ignore
        except Exception as e:
            self.on_error(f"GStreamer not available: {e}")
            return False

        try:
            Gst.init(None)
        except Exception as e:
            self.on_error(f"GStreamer init error: {e}")
            return False

        # Optimized H264/RTP pipeline (low-latency, fail-soft).
        desc = (
            f'udpsrc port={self.port} caps="application/x-rtp, media=video, encoding-name=H264, payload=96, '
            f'clock-rate=90000" '
            f"! rtpjitterbuffer latency={self.latency_ms} drop-on-late=true "
            f"! rtph264depay "
            f"! h264parse "
            f"! avdec_h264 "
            f"! videoconvert "
            f"! videoscale "
            f"! video/x-raw,format=BGRA,width=1280,height=720 "
            f"! appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false"
        )

        try:
            pipeline = Gst.parse_launch(desc)
            appsink = pipeline.get_by_name("sink")
            if appsink is None:
                self.on_error("Invalid video pipeline (missing appsink).")
                return False

            def _on_new_sample(sink):
                try:
                    sample = sink.emit("pull-sample")
                    buf = sample.get_buffer()
                    caps = sample.get_caps()
                    s = caps.get_structure(0)
                    width = int(s.get_value("width"))
                    height = int(s.get_value("height"))
                    ok, mapinfo = buf.map(Gst.MapFlags.READ)
                    if not ok:
                        return Gst.FlowReturn.OK
                    try:
                        # NOTE: True zero-copy is not safe here because we unmap the buffer
                        # before the Qt thread consumes it. We keep a single allocation per frame.
                        data = bytes(mapinfo.data)
                    finally:
                        buf.unmap(mapinfo)

                    self.on_frame(VideoFrame(width=width, height=height, rgb_bytes=data))
                except Exception:
                    # keep pipeline alive; errors will surface via bus
                    pass
                return Gst.FlowReturn.OK

            appsink.connect("new-sample", _on_new_sample)

            self._pipeline = pipeline
            self._running = True

            # Bus monitoring (Qt app doesn't run GLib loop -> poll bus in a thread).
            try:
                self._bus = pipeline.get_bus()
            except Exception:
                self._bus = None

            self._stop_bus.clear()

            def _bus_watch() -> None:
                def _emit_error(msg: str) -> None:
                    # Suppress errors during shutdown to avoid noisy logs on app close.
                    if self._stop_bus.is_set() or (not self._running):
                        return
                    self.on_error(msg)

                try:
                    mask = Gst.MessageType.ERROR | Gst.MessageType.EOS
                    while not self._stop_bus.is_set() and self._running and self._pipeline is pipeline:
                        bus = self._bus
                        if bus is None:
                            break
                        msg = bus.timed_pop_filtered(50 * Gst.MSECOND, mask)
                        if msg is None:
                            continue
                        if msg.type == Gst.MessageType.EOS:
                            _emit_error("Video: stream ended (EOS).")
                            break
                        if msg.type == Gst.MessageType.ERROR:
                            err, dbg = msg.parse_error()
                            details = f"{err}"
                            if dbg:
                                details = f"{details} ({dbg})"
                            _emit_error(f"Video: GStreamer error: {details}")
                            break
                except Exception as e:
                    _emit_error(f"Video: bus monitor error: {e}")
                finally:
                    # Best-effort cleanup; UI side handles retry scheduling.
                    try:
                        if self._pipeline is pipeline:
                            pipeline.set_state(Gst.State.NULL)
                    except Exception:
                        pass

            self._bus_thread = threading.Thread(target=_bus_watch, daemon=True)
            self._bus_thread.start()

            pipeline.set_state(Gst.State.PLAYING)
            return True
        except Exception as e:
            self.on_error(f"Unable to start video pipeline: {e}")
            self._pipeline = None
            self._running = False
            return False

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_bus.set()
        try:
            import gi  # type: ignore

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst  # type: ignore
        except Exception:
            self._pipeline = None
            self._bus = None
            return

        try:
            if self._pipeline is not None:
                self._pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        finally:
            self._pipeline = None
            self._bus = None
            t = self._bus_thread
            self._bus_thread = None
            if t is not None and t.is_alive():
                try:
                    t.join(timeout=0.6)
                except Exception:
                    pass
