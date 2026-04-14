from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QGuiApplication, QImage, QKeyEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ...core.config import load_config
from ...core.events import (
    CarsEvent,
    ErrorEvent,
    LogEvent,
    MozaStateEvent,
    ScanDoneEvent,
    SessionStoppedEvent,
    StatusEvent,
    TelemetryEvent,
)
from ...core.models import Car
from ...core.settings import SettingsStore
from ...core.state import AppPhase
from ...ports.video import VideoFrame, VideoReceiver, VideoReceiverFactory
from ..components.banner import build_banner
from ..components.docks import build_debug_docks, build_log_panel
from ..components.header import build_header
from ..components.hud import build_hud, format_moza_badge
from ..strings import UI
from ._cars_panel import CarsPanel
from ._log_panel import LogPanel
from ._queue_drain import drain_queue
from ._session_panel import SessionPanel


class SessionControllerPort(Protocol):
    events: queue.Queue
    scan_thread: threading.Thread | None
    drive_thread: threading.Thread | None

    def start_scan(self) -> bool: ...
    def cancel_scan(self) -> bool: ...
    def connect(self, car: Car) -> bool: ...
    def disconnect(self) -> None: ...
    def shutdown(self) -> None: ...


@dataclass
class CarRow:
    name: str
    ip: str
    control_port: int
    video_port: int


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        video_receiver_factory: VideoReceiverFactory | None = None,
        settings: SettingsStore | None = None,
        controller: SessionControllerPort,
    ):
        super().__init__()
        self.cfg = load_config()
        self.settings = settings
        self._video_receiver_factory = video_receiver_factory

        self.controller = controller
        self.ui_queue = self.controller.events

        self.phase: AppPhase = AppPhase.IDLE
        self.cars: list[Car] = []
        self.filtered_indices: list[int] = []
        self.selected_index: int | None = None

        self.is_connected = False
        self.video_active = False
        self.is_scanning = False
        self.is_connecting = False
        self.active_car_id: str | None = None
        self._video_receiver: VideoReceiver | None = None
        self._video_port_last: int | None = None
        self._video_missing_deps: bool = False
        self._video_retry_ms = 500
        self._video_retry_enabled = True
        self._video_last_error: str | None = None
        self._video_last_error_ts_ms: int = 0

        self._last_telemetry: dict = {}
        self._telemetry_trace: list[dict] = []
        self._autoconnect_seq: int = 0
        self._autoconnect_pending: bool = False

        self._layout_transition_in_progress: bool = False
        self._layout_transition_current: str | None = None
        self._layout_transition_queued: str | None = None
        self._pulse_timer: QTimer | None = None
        self._pulse_on: bool = False
        self._splitter_save_timer: QTimer | None = None
        self._banner_token: int = 0
        self._fade_anim: QVariantAnimation | None = None
        self._closing: bool = False
        self._pre_drive_was_maximized: bool = False
        self._startup_layout_id: str = "A"
        self._did_initial_window_restore: bool = False
        self._shutdown_overlay: QWidget | None = None

        self.setWindowTitle("RC Simulator")
        self.resize(1280, 800)

        # Frameless everywhere (enterprise chrome is implemented in our title bar).
        # Wayland/WSLg instability is handled by avoiding window-state transitions there
        # (fullscreen/maximize/restoreState), not by switching chrome style.
        self.setWindowFlag(Qt.FramelessWindowHint, True)

        self._build_ui()
        self._install_shortcuts()
        # Wayland/WSLg: restoring maximized/fullscreen before the first show can produce 0x0
        # configure events and crash the connection. Defer restore + initial layout until showEvent.
        self._startup_layout_id = self._resolve_layout_id()

        self.timer = QTimer(self)
        self.timer.setInterval(self.cfg.queue_poll_ms)
        self.timer.timeout.connect(self.process_ui_queue)
        self.timer.start()

        self._init_premium_polish()

        if bool(getattr(self.cfg, "auto_scan", True)):
            self.start_scan()

    def showEvent(self, event) -> None:
        # One-time: restore window state + enforce startup layout after the window exists.
        if not self._did_initial_window_restore:
            self._did_initial_window_restore = True

            def _restore_and_apply() -> None:
                try:
                    self._restore_window_state()
                finally:
                    # Enforce the chosen layout after restoreState(), which may re-show docks.
                    # Apply without animation to keep startup consistent (and avoid visible flicker).
                    self._apply_layout_now(str(self._startup_layout_id or "A"))
                    # Startup coherence: force overlay/guard state immediately so no placeholder
                    # text bleeds through on the very first frame.
                    try:
                        self._refresh_video_overlay()
                    except Exception:
                        pass
                    try:
                        self._apply_drive_guard_state()
                    except Exception:
                        pass

            # Wayland/WSLg: showEvent can still arrive before a non-zero configure is settled.
            # Wait until the window has a non-zero size before any window-state transitions.
            self._run_when_window_has_size(_restore_and_apply)
        super().showEvent(event)

    def _is_wayland(self) -> bool:
        try:
            return "wayland" in str(QGuiApplication.platformName() or "").lower()
        except Exception:
            return False

    def _run_when_window_has_size(self, fn, *, tries: int = 60, delay_ms: int = 16) -> None:
        """
        Wayland/WSLg can deliver maximized/fullscreen configure events with 0x0 early in startup.
        Wait until the window has a non-zero size before running state-changing operations.
        """

        def _tick(n: int) -> None:
            try:
                if self.width() > 0 and self.height() > 0:
                    fn()
                    return
            except Exception:
                pass
            if n <= 0:
                fn()
                return
            QTimer.singleShot(int(delay_ms), lambda: _tick(n - 1))

        QTimer.singleShot(0, lambda: _tick(int(tries)))

    def _init_premium_polish(self) -> None:
        # Pulse timer: only active while scanning/connecting.
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(450)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)

        # Keep HUD simple: avoid QGraphicsEffects (can cause platform-specific QPainter warnings).
        # If we want dimming, do it via QSS/properties instead.

    def _level_to_kind(self, lvl: str) -> str:
        u = (lvl or "INFO").upper()
        if u == "ERROR":
            return "danger"
        if u in ("WARN", "WARNING"):
            return "warn"
        if u in ("OK", "SUCCESS"):
            return "ok"
        return "muted"

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        # Central content container. We animate THIS widget (not the OS window)
        # to avoid flicker with showFullScreen()/window manager repaints.
        root = QWidget(self)
        self._central_stack = root
        self._root = root
        root_layout = QVBoxLayout(root)
        if self.cfg.density == "compact":
            root_layout.setContentsMargins(10, 10, 10, 10)
            root_layout.setSpacing(8)
        else:
            root_layout.setContentsMargins(12, 12, 12, 12)
            root_layout.setSpacing(10)

        # Header
        header = build_header(
            parent=root,
            on_toggle_drive_mode=self.toggle_drive_mode,
            on_toggle_debug_mode=self.toggle_debug_mode,
            on_minimize=self.showMinimized,
            on_maximize_restore=self._toggle_maximize_restore,
            on_close=self.close,
            on_start_move=self._start_system_move,
        )
        self.header_widget = header.widget
        self.title_label = header.title
        self.badge_scan = header.badge_scan
        self.badge_conn = header.badge_conn
        self.badge_moza = header.badge_moza
        self.badge_video = header.badge_video
        self.badge_output = header.badge_output
        self.btn_drive = header.btn_drive
        self.btn_debug = header.btn_debug
        self.btn_win_min = header.btn_min
        self.btn_win_max = header.btn_max
        self.btn_win_close = header.btn_close

        # Icons (built-in, no extra deps)
        self.btn_drive.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_debug.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))

        root_layout.addWidget(self.header_widget)

        # Non-modal banner (warnings/errors) under header
        header_banner = build_banner(parent=root, on_close=self._hide_banner)
        self.banner = header_banner.widget
        self.banner_text = header_banner.text
        self.banner_close = header_banner.close_button
        root_layout.addWidget(self.banner)

        # Center content: left panel + center placeholder. Right is dock (log)
        center = QWidget(root)
        center_l = QHBoxLayout(center)
        center_l.setContentsMargins(0, 0, 0, 0)
        center_l.setSpacing(8 if self.cfg.density == "compact" else 10)

        # Left panel
        self.left_panel = QWidget(center)
        self.left_panel.setMinimumWidth(280)
        left_l = QVBoxLayout(self.left_panel)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(6 if self.cfg.density == "compact" else 8)

        self.search = QLineEdit(self.left_panel)
        self.search.setPlaceholderText(UI.search_placeholder)
        self.search.textChanged.connect(self._debounce_apply_car_filter)
        left_l.addWidget(self.search)

        self.list_hint = QLabel(UI.list_hint, self.left_panel)
        self.list_hint.setObjectName("muted")
        self.list_hint.setWordWrap(True)
        self.list_hint.setVisible(False)
        # Empty-state and guidance belong directly under Search.
        left_l.addWidget(self.list_hint)

        # Left stack: cars list (top) + system log (bottom).
        self.left_splitter = QSplitter(Qt.Vertical, self.left_panel)
        self.left_splitter.setChildrenCollapsible(False)
        left_l.addWidget(self.left_splitter, 1)

        self.list = QListWidget(self.left_panel)
        self.list.itemSelectionChanged.connect(self.on_select)
        self.left_splitter.addWidget(self.list)

        btn_row = QWidget(self.left_panel)
        btn_row_l = QHBoxLayout(btn_row)
        btn_row_l.setContentsMargins(0, 0, 0, 0)
        self.btn_scan = QPushButton(UI.scan_button, btn_row)
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_scan.setToolTip(UI.scan_tooltip)
        self.btn_connect = QPushButton(UI.connect_button, btn_row)
        self.btn_connect.setObjectName("primaryButton")
        self.btn_connect.clicked.connect(self.connect_selected)
        self.btn_connect.setToolTip(UI.connect_tooltip)
        self.btn_disconnect = QPushButton(UI.disconnect_button, btn_row)
        self.btn_disconnect.setObjectName("dangerButton")
        self.btn_disconnect.clicked.connect(self.disconnect_session)
        self.btn_disconnect.setToolTip(UI.disconnect_tooltip)
        btn_row_l.addWidget(self.btn_scan)
        btn_row_l.addWidget(self.btn_connect)
        btn_row_l.addWidget(self.btn_disconnect)
        left_l.addWidget(btn_row)

        self.btn_scan.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_connect.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_disconnect.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))

        # Layout A balance: center is the "hero", sidebar stays flexible.
        center_l.addWidget(self.left_panel, 1)

        # Center panel (session/video/telemetry placeholder in v1)
        self.mid_panel = QWidget(center)
        mid_l = QVBoxLayout(self.mid_panel)
        mid_l.setContentsMargins(0, 0, 0, 0)
        mid_l.setSpacing(8 if self.cfg.density == "compact" else 10)

        # Mid empty-state card (operator guidance)
        self.mid_state = QWidget(self.mid_panel)
        self.mid_state.setObjectName("midState")
        ms_l = QVBoxLayout(self.mid_state)
        if self.cfg.density == "compact":
            ms_l.setContentsMargins(12, 12, 12, 12)
            ms_l.setSpacing(8)
        else:
            ms_l.setContentsMargins(14, 14, 14, 14)
            ms_l.setSpacing(10)

        self.mid_state_title = QLabel(UI.mid_ready, self.mid_state)
        self.mid_state_title.setObjectName("title")
        self.mid_state_body = QLabel("", self.mid_state)
        self.mid_state_body.setWordWrap(True)
        self.mid_state_body.setObjectName("muted")
        ms_l.addWidget(self.mid_state_title)
        ms_l.addWidget(self.mid_state_body)

        mid_l.addWidget(self.mid_state)

        self.session_label = QLabel(UI.session_status_ready, self.mid_panel)
        self.detail_label = QLabel("", self.mid_panel)
        self.phase_progress = QProgressBar(self.mid_panel)
        self.phase_progress.setRange(0, 0)
        self.phase_progress.setTextVisible(False)
        self.phase_progress.setFixedHeight(10)
        self.phase_progress.setVisible(False)

        self.telemetry_label = QLabel(UI.session_inactive, self.mid_panel)
        self.telemetry_label.setWordWrap(True)
        mid_l.addWidget(self.session_label)
        mid_l.addWidget(self.detail_label)
        mid_l.addWidget(self.phase_progress)
        self.live_video_label = QLabel(UI.live_video_label, self.mid_panel)
        mid_l.addWidget(self.live_video_label)

        self.video_container = QWidget(self.mid_panel)
        self.video_container.setMinimumHeight(240)
        grid = QGridLayout(self.video_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self.video_view = QLabel(UI.video_not_available, self.video_container)
        self.video_view.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.video_view, 0, 0, 1, 1)

        # Center overlay for video state (better than a bottom-left label).
        self.video_overlay = QWidget(self.video_container)
        self.video_overlay.setObjectName("videoOverlay")
        vo_l = QVBoxLayout(self.video_overlay)
        if self.cfg.density == "compact":
            vo_l.setContentsMargins(14, 14, 14, 14)
            vo_l.setSpacing(8)
        else:
            vo_l.setContentsMargins(16, 16, 16, 16)
            vo_l.setSpacing(10)
        vo_l.addStretch(1)
        self.video_overlay_title = QLabel("Video", self.video_overlay)
        self.video_overlay_title.setObjectName("videoOverlayTitle")
        self.video_overlay_title.setAlignment(Qt.AlignHCenter)
        self.video_overlay_body = QLabel("", self.video_overlay)
        self.video_overlay_body.setObjectName("muted")
        self.video_overlay_body.setWordWrap(True)
        self.video_overlay_body.setAlignment(Qt.AlignHCenter)
        self.video_overlay_action = QPushButton("", self.video_overlay)
        self.video_overlay_action.setObjectName("secondaryButton")
        self.video_overlay_action.clicked.connect(self._on_video_overlay_action_clicked)
        vo_l.addWidget(self.video_overlay_title)
        vo_l.addWidget(self.video_overlay_body)
        vo_l.addWidget(self.video_overlay_action, 0, alignment=Qt.AlignHCenter)
        vo_l.addStretch(1)
        self.video_overlay.setVisible(True)
        grid.addWidget(self.video_overlay, 0, 0, 1, 1)

        # Drive guard overlay (Layout B without an active connection).
        self.drive_guard_overlay = QWidget(self.video_container)
        self.drive_guard_overlay.setObjectName("driveGuardOverlay")
        dgo_l = QVBoxLayout(self.drive_guard_overlay)
        if self.cfg.density == "compact":
            dgo_l.setContentsMargins(14, 14, 14, 14)
            dgo_l.setSpacing(8)
        else:
            dgo_l.setContentsMargins(16, 16, 16, 16)
            dgo_l.setSpacing(10)
        dgo_l.addStretch(1)
        self.drive_guard_title = QLabel(UI.drive_guard_title, self.drive_guard_overlay)
        self.drive_guard_title.setObjectName("driveGuardTitle")
        self.drive_guard_title.setAlignment(Qt.AlignHCenter)
        self.drive_guard_body = QLabel(UI.drive_guard_body, self.drive_guard_overlay)
        self.drive_guard_body.setObjectName("muted")
        self.drive_guard_body.setWordWrap(True)
        self.drive_guard_body.setAlignment(Qt.AlignHCenter)
        self.drive_guard_action = QPushButton(UI.dashboard_button, self.drive_guard_overlay)
        self.drive_guard_action.setObjectName("primaryButton")
        self.drive_guard_action.clicked.connect(lambda: self.apply_layout("A"))
        dgo_l.addWidget(self.drive_guard_title)
        dgo_l.addWidget(self.drive_guard_body)
        dgo_l.addWidget(self.drive_guard_action, 0, alignment=Qt.AlignHCenter)
        dgo_l.addStretch(1)
        self.drive_guard_overlay.setVisible(False)
        grid.addWidget(self.drive_guard_overlay, 0, 0, 1, 1)

        self.btn_video_help = QPushButton(UI.video_requirements_button, self.video_container)
        self.btn_video_help.setObjectName("secondaryButton")
        self.btn_video_help.clicked.connect(self._show_video_requirements_hint)
        self.btn_video_help.setToolTip(UI.video_requirements_tooltip)
        self.btn_video_help.setVisible(False)
        grid.addWidget(self.btn_video_help, 0, 0, 1, 1, alignment=Qt.AlignBottom | Qt.AlignRight)

        self.btn_overlay_disconnect = QPushButton(UI.overlay_disconnect_button, self.video_container)
        self.btn_overlay_disconnect.setObjectName("dangerButton")
        self.btn_overlay_disconnect.clicked.connect(self.disconnect_session)
        self.btn_overlay_disconnect.setVisible(False)
        self.btn_overlay_disconnect.setToolTip(UI.overlay_disconnect_tooltip)
        self.btn_overlay_disconnect.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))

        # HUD (Drive Mode): keep essential indicators visible
        hud = build_hud(parent=self.video_container)
        self.hud = hud.widget
        self.hud_conn = hud.conn
        self.hud_moza = hud.moza
        self.hud_video = hud.video
        self.hud_output = hud.output
        # Top-right stack: HUD + disconnect button must never overlap.
        self.drive_top_right = QWidget(self.video_container)
        tr_l = QVBoxLayout(self.drive_top_right)
        tr_l.setContentsMargins(0, 0, 0, 0)
        tr_l.setSpacing(6 if self.cfg.density == "compact" else 8)
        tr_l.addWidget(self.hud, 0, alignment=Qt.AlignRight)
        tr_l.addWidget(self.btn_overlay_disconnect, 0, alignment=Qt.AlignRight)
        tr_l.addStretch(1)
        grid.addWidget(self.drive_top_right, 0, 0, 1, 1, alignment=Qt.AlignTop | Qt.AlignRight)
        # Consistent initial MOZA indicator before first event.
        try:
            self.badge_moza.setText(format_moza_badge(state="unknown"))
            self.hud_moza.setText(format_moza_badge(state="unknown"))
        except Exception:
            pass

        # Drive banner: non-modal alerts visible even in fullscreen (layout B hides header banner)
        drive_banner = build_banner(parent=self.video_container, on_close=self._hide_banner)
        self.drive_banner = drive_banner.widget
        self.drive_banner_text = drive_banner.text
        self.drive_banner_close = drive_banner.close_button
        grid.addWidget(self.drive_banner, 0, 0, 1, 1, alignment=Qt.AlignBottom | Qt.AlignHCenter)

        mid_l.addWidget(self.video_container, 1)
        self.telemetry_caption = QLabel(UI.telemetry_label, self.mid_panel)
        mid_l.addWidget(self.telemetry_caption)
        mid_l.addWidget(self.telemetry_label)

        center_l.addWidget(self.mid_panel, 4)

        root_layout.addWidget(center, 1)

        # Bottom status bar (simple label)
        self.bottom = QLabel("", root)
        self.bottom.setObjectName("muted")
        root_layout.addWidget(self.bottom)

        self.setCentralWidget(root)

        # Fade overlay (cinematic transitions without QGraphicsOpacityEffect).
        self._fade_overlay = QWidget(self)
        self._fade_overlay.setObjectName("fadeOverlay")
        self._fade_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._fade_overlay.hide()
        self._set_fade_overlay_alpha(0.0)

        log_panel = build_log_panel(
            parent=self.left_panel,
            on_filter_changed=self.refresh_log_view,
            on_pause_toggled=self._on_pause_log_toggled,
            on_clear_clicked=self.clear_log,
        )
        self.system_log_panel = log_panel.widget
        self.log_filter = log_panel.filter
        self.log_view = log_panel.view
        self.btn_pause_log = log_panel.pause_button
        self.btn_clear_log = log_panel.clear_button
        self.btn_pause_log.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.btn_clear_log.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.left_splitter.addWidget(self.system_log_panel)
        self.left_splitter.setStretchFactor(0, 3)
        self.left_splitter.setStretchFactor(1, 2)

        # Backwards-compat: some tests and layout logic expect `log_dock` to exist.
        # The system log is now embedded (left panel) rather than a QDockWidget.
        self.log_dock = self.system_log_panel

        # Persist splitter sizes (cars list vs system log).
        try:
            self._restore_left_splitter_sizes()
        except Exception:
            pass
        try:
            self.left_splitter.splitterMoved.connect(lambda _pos, _idx: self._schedule_save_left_splitter_sizes())
        except Exception:
            pass

        debug = build_debug_docks(main_window=self)
        self.telemetry_dock = debug.telemetry_dock
        self.trace_dock = debug.trace_dock
        self.t_out = debug.t_out
        self._steer_bar = debug.steer_bar
        self._gas_bar = debug.gas_bar
        self._brake_bar = debug.brake_bar
        self.telemetry_raw = debug.telemetry_raw
        self.trace_view = debug.trace_view

        self._last_video_pixmap: QPixmap | None = None
        self._log_widget_limit = 500

        self._log_panel = LogPanel(
            cfg=self.cfg,
            log_filter=self.log_filter,
            log_view=self.log_view,
            btn_pause_log=self.btn_pause_log,
            level_to_kind=self._level_to_kind,
            standard_icon=self.style().standardIcon,
            sp_media_pause=int(QStyle.SP_MediaPause),
            sp_media_play=int(QStyle.SP_MediaPlay),
            enforce_widget_limit=int(self._log_widget_limit),
        )

        self._cars_panel = CarsPanel(
            cfg=self.cfg,
            search=self.search,
            list_widget=self.list,
            list_hint=self.list_hint,
            get_cars=lambda: self.cars,
            get_active_car_id=lambda: self.active_car_id,
            get_preferred_ip=lambda: (
                str(self.settings.value("ui/lastSelectedCarIp", "") or "").strip()
                if self.settings is not None
                else None
            ),
            set_filtered_indices=lambda v: setattr(self, "filtered_indices", v),
            set_selected_index=lambda v: setattr(self, "selected_index", v),
            get_filtered_indices=lambda: self.filtered_indices,
            get_selected_index=lambda: self.selected_index,
            on_selection_changed=self._update_controls,
            on_after_filter_applied=lambda: (self._update_controls(), self._refresh_mid_state()),
        )

        self._session_panel = SessionPanel(
            settings=self.settings,
            controller=self.controller,
            btn_drive=self.btn_drive,
            btn_scan=self.btn_scan,
            btn_connect=self.btn_connect,
            btn_disconnect=self.btn_disconnect,
            btn_overlay_disconnect=self.btn_overlay_disconnect,
            hud=self.hud,
            phase_progress=self.phase_progress,
            mid_state=self.mid_state,
            mid_state_title=self.mid_state_title,
            mid_state_body=self.mid_state_body,
            bottom=self.bottom,
            get_is_fullscreen=self.isFullScreen,
            refresh_video_overlay=self._refresh_video_overlay,
        )

        self._update_controls()
        self._update_left_hint()
        self._refresh_mid_state()
        self._refresh_video_overlay()
        self._update_bottom_hint()
        try:
            self._sync_header_nav_buttons(
                str(self.settings.value("layout_id", "A")) if self.settings is not None else "A"
            )
        except Exception:
            pass

        # Predictable keyboard navigation (accessibility + operator UX).
        try:
            QWidget.setTabOrder(self.search, self.list)
            QWidget.setTabOrder(self.list, self.log_filter)
            QWidget.setTabOrder(self.log_filter, self.log_view)
            QWidget.setTabOrder(self.log_view, self.btn_pause_log)
            QWidget.setTabOrder(self.btn_pause_log, self.btn_clear_log)
            QWidget.setTabOrder(self.btn_clear_log, self.btn_scan)
            QWidget.setTabOrder(self.btn_scan, self.btn_connect)
            QWidget.setTabOrder(self.btn_connect, self.btn_disconnect)
        except Exception:
            pass

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.clear_log)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.connect_selected)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, activated=self.focus_log_filter)
        QShortcut(QKeySequence(Qt.Key_F1), self, activated=self.show_shortcuts_help)
        # Esc handled via keyPressEvent for deterministic priority logic.

    def show_shortcuts_help(self) -> None:
        self._show_banner(
            "muted",
            UI.shortcuts_help,
            auto_hide_ms=12_000,
        )

    def _update_bottom_hint(self) -> None:
        self._session_panel.update_bottom_hint(is_connected=bool(self.is_connected))

    # ---------------- Persistence / layouts ----------------
    def _restore_layout(self) -> None:
        if self.settings is None:
            return
        self.apply_layout(self._resolve_layout_id())

    def _resolve_layout_id(self) -> str:
        """
        Single source of truth for the effective layout at startup.

        `start_layout` (config) overrides persisted `layout_id`.
        """
        start_layout = str(getattr(self.cfg, "start_layout", "") or "").strip()
        if start_layout in ("A", "B", "C"):
            return start_layout
        if self.settings is None:
            return "A"
        layout_id = str(self.settings.value("layout_id", self.cfg.default_layout))
        return layout_id if layout_id in ("A", "B", "C") else "A"

    def _toggle_maximize_restore(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _start_system_move(self) -> None:
        # Best-effort: delegate move to the window manager.
        try:
            wh = self.windowHandle()
            if wh is not None:
                wh.startSystemMove()
        except Exception:
            pass

    def apply_layout(self, layout_id: str) -> None:
        if self.settings is None:
            return
        # Avoid re-entrant transitions (e.g., repeated hotkeys).
        if self._layout_transition_in_progress:
            self._layout_transition_queued = layout_id
            return

        # If we're not visible yet, apply immediately (no animation).
        if not self.isVisible():
            self._apply_layout_now(layout_id)
            return

        # Safety: avoid layout transition animation while connecting/disconnecting.
        # Some compositors (Wayland/WSLg) are fragile during rapid state changes.
        if bool(self.is_connecting) or bool(self.phase == AppPhase.DISCONNECTING):
            self._apply_layout_now(layout_id)
            return

        self._layout_transition_in_progress = True
        self._layout_transition_current = layout_id
        self._layout_transition_queued = None

        def _after_fade_out() -> None:
            try:
                self._apply_layout_now(layout_id)
            finally:
                # Fade back in, then allow next transition if queued.
                QTimer.singleShot(
                    0,
                    lambda: self._fade_overlay_to(
                        0.0,
                        ms=200,
                        on_done=self._on_layout_fade_in_done,
                    ),
                )

        self._fade_overlay_to(1.0, ms=200, on_done=_after_fade_out)

    def _on_layout_fade_in_done(self) -> None:
        self._layout_transition_in_progress = False
        current = self._layout_transition_current
        queued = self._layout_transition_queued
        self._layout_transition_current = None
        self._layout_transition_queued = None
        if queued is not None and queued != current:
            self.apply_layout(queued)

    def _apply_layout_now(self, layout_id: str) -> None:
        if self.settings is None:
            return
        # Reduce flicker during window-state changes (frameless/fullscreen).
        # Important: layout changes happen while central content is fully faded out.
        self.setUpdatesEnabled(False)
        try:
            # Normalize + persist layout id early (single source of truth).
            layout_id = layout_id if layout_id in ("A", "B", "C") else "A"
            self.settings.setValue("layout_id", layout_id)
            if layout_id == "B":
                # ---------------- Drive Mode (layout B) ----------------
                self._pre_drive_was_maximized = bool(self.isMaximized())
                self.btn_drive.setChecked(True)
                self.btn_debug.setChecked(False)
                self._sync_header_nav_buttons(layout_id)

                # Hide everything non-essential
                self.header_widget.hide()
                self.banner.hide()
                self.left_panel.hide()
                self.bottom.hide()
                self.telemetry_dock.hide()
                self.trace_dock.hide()

                # Essential Drive overlays
                self.hud.setVisible(True)
                # Pure focus: only 3 signals (STATE/MOZA/VIDEO)
                self.hud_output.setVisible(False)
                self.btn_overlay_disconnect.setVisible(bool(self.is_connected))
                self.drive_guard_overlay.setVisible(not bool(self.is_connected))
                # Dashboard-only labels: hide in Drive to avoid visual overlap with overlays.
                try:
                    self.live_video_label.setVisible(False)
                    self.telemetry_caption.setVisible(False)
                    self.telemetry_label.setVisible(False)
                except Exception:
                    pass
                # Drive guard: suppress underlying "video not available" text behind the translucent overlay.
                try:
                    if not bool(self.is_connected):
                        self.video_view.setVisible(False)
                        self.video_overlay.setVisible(False)
                    else:
                        self.video_view.setVisible(True)
                        # video_overlay is managed by _refresh_video_overlay() based on frames
                except Exception:
                    pass
                # Drive guard: show an explicit escape hatch only when disconnected.
                try:
                    self.drive_guard_action.setVisible(not bool(self.is_connected))
                except Exception:
                    pass
                # Make guard state fully deterministic on entry (no bleed-through).
                try:
                    self._apply_drive_guard_state()
                except Exception:
                    pass
                # `drive_banner` visibility is controlled by _show_banner() based on drive layout.
                self.drive_banner.setVisible(False)

                # Deterministic layering (bottom->top): video, guard, HUD/banners/disconnect
                try:
                    self.drive_guard_overlay.raise_()
                    self.hud.raise_()
                    self.btn_overlay_disconnect.raise_()
                    self.drive_banner.raise_()
                except Exception:
                    pass

                # Wayland/WSLg is fragile with fullscreen transitions.
                # - Wayland/WSLg: borderless maximized (frameless + maximized)
                # - X11: fullscreen
                if self._is_wayland():
                    # Avoid redundant maximized transitions to reduce compositor flicker.
                    if not self.isMaximized():
                        self._run_when_window_has_size(self.showMaximized)
                else:
                    self._run_when_window_has_size(self.showFullScreen)
                # Safety hint: frameless fullscreen needs a clear escape hatch.
                self._show_banner("muted", UI.drive_mode_hint, auto_hide_ms=0)
                self._update_bottom_hint()
            else:
                # ---------------- Panel/Debug (layouts A/C) ----------------
                # Exit Drive Mode: restore the operator's prior window state.
                if not self._is_wayland():
                    if self._pre_drive_was_maximized:
                        self._run_when_window_has_size(self.showMaximized)
                    else:
                        self._run_when_window_has_size(self.showNormal)
                self.btn_drive.setChecked(False)
                self.btn_overlay_disconnect.setVisible(False)
                self.hud.setVisible(False)
                self.drive_banner.setVisible(False)
                self.drive_guard_overlay.setVisible(False)
                self.hud_output.setVisible(True)
                try:
                    self.live_video_label.setVisible(True)
                    self.telemetry_caption.setVisible(True)
                    self.telemetry_label.setVisible(True)
                except Exception:
                    pass
                try:
                    self.video_view.setVisible(True)
                    self._refresh_video_overlay()
                except Exception:
                    pass
                try:
                    self.drive_guard_action.setVisible(True)
                except Exception:
                    pass

                # Show normal chrome
                self.header_widget.show()
                self.banner.setVisible(bool(self.banner_text.text().strip()))
                self.left_panel.show()
                self.bottom.show()
                if layout_id == "C":
                    self.telemetry_dock.show()
                    self.trace_dock.show()
                    self.btn_debug.setChecked(True)
                else:
                    self.btn_debug.setChecked(False)
                    self.telemetry_dock.hide()
                    self.trace_dock.hide()
                self._sync_header_nav_buttons(layout_id)
                self._update_bottom_hint()
        finally:
            self.setUpdatesEnabled(True)

    def _sync_header_nav_buttons(self, layout_id: str) -> None:
        """
        Senior UX: header button text shows the destination (what happens on click).
        - In Drive (B): Drive button shows "Dashboard"
        - In Panels (C): Panels button shows "Dashboard"
        - In Dashboard (A): show "Drive" and "Panels"
        """
        if layout_id == "B":
            self.btn_drive.setText(UI.dashboard_button)
            self.btn_drive.setToolTip(UI.dashboard_tooltip)
            self.btn_debug.setText(UI.panels_button)
            self.btn_debug.setToolTip(UI.panels_tooltip)
            return
        if layout_id == "C":
            self.btn_drive.setText(UI.drive_button)
            self.btn_drive.setToolTip(UI.drive_tooltip)
            self.btn_debug.setText(UI.dashboard_button)
            self.btn_debug.setToolTip(UI.dashboard_tooltip)
            return
        # A (Dashboard)
        self.btn_drive.setText(UI.drive_button)
        self.btn_drive.setToolTip(UI.drive_tooltip)
        self.btn_debug.setText(UI.panels_button)
        self.btn_debug.setToolTip(UI.panels_tooltip)

    def _set_fade_overlay_alpha(self, a: float) -> None:
        a = 0.0 if a < 0.0 else (1.0 if a > 1.0 else a)
        # Single source of truth for the current overlay alpha.
        self._fade_overlay_alpha = float(a)
        # Obsidian fade. Keep it subtle (not pure black).
        alpha = int(a * 255)
        self._fade_overlay.setStyleSheet(f"background: rgba(15, 23, 42, {alpha}); border: none;")
        if alpha <= 0:
            self._fade_overlay.hide()
        else:
            # Ensure geometry is valid before showing; otherwise some platforms
            # can end up with a full-window opaque overlay until the first resizeEvent.
            try:
                self._fade_overlay.setGeometry(0, 0, self.width(), self.height())
            except Exception:
                pass
            self._fade_overlay.show()
            self._fade_overlay.raise_()

    def _fade_overlay_to(self, end: float, *, ms: int = 200, on_done=None) -> None:
        if self._fade_overlay is None:
            if callable(on_done):
                on_done()
            return
        if self._fade_anim is not None:
            try:
                self._fade_anim.stop()
            except Exception:
                pass
        start = float(getattr(self, "_fade_overlay_alpha", 0.0))
        end = float(end)

        def _on_value(v: float) -> None:
            self._fade_overlay_alpha = float(v)
            self._set_fade_overlay_alpha(float(v))

        if int(ms) <= 0 or start == end:
            _on_value(end)
            if callable(on_done):
                on_done()
            return

        anim = QVariantAnimation(self)
        anim.setDuration(int(ms))
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.valueChanged.connect(_on_value)
        if callable(on_done):
            anim.finished.connect(on_done)
        self._fade_anim = anim
        # Apply initial value immediately to avoid a "stuck opaque overlay" if the
        # platform delays the first animation tick.
        _on_value(start)
        anim.start()

    def start_reveal(self, *, ms: int = 300) -> None:
        """
        Premium startup reveal. Animates central content only (not OS window)
        to avoid platform plugins that don't support window opacity.
        """
        # Reveal = fade overlay from opaque -> transparent.
        self._set_fade_overlay_alpha(1.0)
        QTimer.singleShot(0, lambda: self._fade_overlay_to(0.0, ms=int(ms)))

    def toggle_drive_mode(self) -> None:
        self.apply_layout("B" if self.btn_drive.isChecked() else "A")

    def toggle_debug_mode(self) -> None:
        self.apply_layout("C" if self.btn_debug.isChecked() else "A")

    # ---------------- Core actions ----------------
    def start_scan(self) -> None:
        # If a scan is already running, Scan acts as Cancel.
        if bool(self.is_scanning) or (
            self.controller.scan_thread is not None and self.controller.scan_thread.is_alive()
        ):
            self.cancel_scan()
            return
        if self.controller.drive_thread is not None and self.controller.drive_thread.is_alive():
            self._show_banner("warn", UI.active_session_disconnect_first)
            return
        if self.controller.scan_thread is not None and self.controller.scan_thread.is_alive():
            return
        self.is_scanning = True
        self._apply_primary_state_badge(AppPhase.SCANNING)
        self._update_left_hint()
        self._update_controls()
        started = self.controller.start_scan()
        if not started:
            self.is_scanning = False
            self._apply_primary_state_badge(AppPhase.IDLE)
            self._update_left_hint()
            self._update_controls()
        self._refresh_pulse_state()

    def cancel_scan(self) -> None:
        if self.controller.scan_thread is None or (not self.controller.scan_thread.is_alive()):
            return
        cancelled = False
        try:
            cancelled = bool(self.controller.cancel_scan())
        except Exception:
            cancelled = False
        if cancelled:
            # Keep showing SCANNING until ScanDoneEvent arrives.
            self.is_scanning = True
            self._apply_primary_state_badge(AppPhase.SCANNING)
            self._update_left_hint()
            self._update_controls()

    def connect_selected(self) -> None:
        if self.controller.drive_thread is not None and self.controller.drive_thread.is_alive():
            self._show_banner("muted", UI.session_already_active)
            return
        if self.controller.scan_thread is not None and self.controller.scan_thread.is_alive():
            self._show_banner("muted", UI.scan_in_progress_wait_or_cancel)
            return
        if not self.cars:
            self._show_banner("warn", UI.no_cars_found_scan_first)
            return
        if self.selected_index is None:
            self._show_banner("warn", UI.missing_selection)
            return
        if not (0 <= self.selected_index < len(self.filtered_indices)):
            self._show_banner("warn", UI.missing_selection)
            return
        car = self.cars[self.filtered_indices[self.selected_index]]
        self.active_car_id = str(car.ip or "")
        self._refresh_car_row_active_styles()

        self.session_label.setText(f"{UI.session_status_prefix}{UI.connect_button_connecting}")
        self.detail_label.setText(f"{car.name} ({car.ip}:{car.control_port})")
        self.badge_moza.setText(format_moza_badge(state="wait"))
        self.is_connecting = True
        self._apply_primary_state_badge(AppPhase.CONNECTING)
        self._update_controls()

        ok = self.controller.connect(car)
        if not ok:
            self.is_connecting = False
            self._apply_primary_state_badge(AppPhase.IDLE)
            self._update_controls()
            self._show_banner("warn", UI.unable_start_session_active)
            return
        self._start_video_for_car(car)
        # In Drive mode we force fullscreen.
        if self.btn_drive.isChecked():
            self.apply_layout("B")
        self._refresh_pulse_state()

    def disconnect_session(self) -> None:
        drive_alive = self.controller.drive_thread is not None and self.controller.drive_thread.is_alive()
        scan_alive = self.controller.scan_thread is not None and self.controller.scan_thread.is_alive()
        if not drive_alive and not scan_alive:
            self.session_label.setText(f"{UI.session_status_prefix}{UI.session_inactive}")
            self.set_connection_state(False)
            self.badge_moza.setText(format_moza_badge(state="unknown"))
            self.active_car_id = None
            self._refresh_car_row_active_styles()
            self.is_connecting = False
            self._update_controls()
            return
        self.append_log("WARN", UI.disconnect_requested)
        self._apply_primary_state_badge(AppPhase.DISCONNECTING)
        try:
            self.controller.disconnect()
        except Exception:
            pass
        self._refresh_pulse_state()

    def set_connection_state(self, connected: bool) -> None:
        self.is_connected = connected
        self._apply_primary_state_badge(AppPhase.CONNECTED if connected else AppPhase.IDLE)
        self.btn_connect.setEnabled(not connected)
        # Overlay disconnect must always be accessible in Drive Mode (fullscreen or windowed).
        if self.btn_drive.isChecked():
            self.btn_overlay_disconnect.setVisible(connected)
            self.hud.setVisible(True)
            # Senior guard: ensure the drive guard + underlying video layers are coherent immediately,
            # without waiting for the next timer tick (prevents "Video not available" bleed-through).
            self._apply_drive_guard_state()
        self._update_controls()
        self._update_bottom_hint()
        self._refresh_pulse_state()

    def _apply_drive_guard_state(self) -> None:
        """
        Drive Mode (Layout B) guard coherence:
        - When disconnected: guard visible, show Dashboard escape hatch, hide underlying video layers.
        - When connected: guard hidden, allow video layers managed by _refresh_video_overlay().
        """
        if not self.btn_drive.isChecked():
            return
        disconnected = not bool(self.is_connected)
        try:
            self.drive_guard_overlay.setVisible(disconnected)
        except Exception:
            pass
        try:
            self.drive_guard_action.setVisible(disconnected)
        except Exception:
            pass
        try:
            if disconnected:
                self.video_view.setVisible(False)
                self.video_overlay.setVisible(False)
            else:
                self.video_view.setVisible(True)
                self._refresh_video_overlay()
        except Exception:
            pass

    def _apply_primary_state_badge(self, phase: AppPhase) -> None:
        """
        Single source of truth for the *one* state badge in the header (and HUD).
        """
        # Never show the legacy scan badge; keep the header minimal.
        try:
            if getattr(self, "badge_scan", None) is not None:
                self.badge_scan.setVisible(False)
        except Exception:
            pass

        text = UI.badge_disconnected
        kind = "warn"
        if phase == AppPhase.SCANNING:
            text = UI.badge_scanning
            kind = "warn"
        elif phase == AppPhase.CONNECTING:
            text = UI.badge_connecting
            kind = "accent"
        elif phase == AppPhase.DISCONNECTING:
            text = UI.badge_disconnecting
            kind = "muted"
        elif phase == AppPhase.CONNECTED:
            text = UI.badge_connected
            kind = "ok"

        self.badge_conn.setText(text)
        self._set_badge_kind(self.badge_conn, kind)
        self.hud_conn.setText(text)
        self._set_badge_kind(self.hud_conn, kind)

    def _update_controls(self) -> None:
        has_selection = self.selected_index is not None and 0 <= int(self.selected_index) < len(self.filtered_indices)
        self._session_panel.update_controls(
            cars_present=bool(self.cars),
            has_selection=bool(has_selection),
            is_connecting=bool(self.is_connecting),
            is_scanning=bool(self.is_scanning),
            is_connected=bool(self.is_connected),
            filtered_indices_len=int(len(self.filtered_indices)),
            selected_index=self.selected_index,
        )
        # Reduce duplicated status: header badges are primary.
        # Keep detailed status only while scanning/connecting/connected.
        show_status = bool(self.is_scanning or self.is_connecting or self.is_connected)
        if self.session_label.isVisible() != show_status:
            self.session_label.setVisible(show_status)
        if self.detail_label.isVisible() != show_status:
            self.detail_label.setVisible(show_status)
        self._refresh_mid_state()
        self._update_left_hint()

    def _update_left_hint(self) -> None:
        # One compact hint under Search; avoid duplicated status elsewhere.
        if self.is_connected:
            self.list_hint.setVisible(False)
            return
        if self.is_scanning:
            self.list_hint.setText(UI.list_hint_scanning)
            self.list_hint.setVisible(True)
            return
        if self.cars:
            self.list_hint.setText(UI.list_hint_found.format(count=len(self.cars)))
            self.list_hint.setVisible(True)
            return
        self.list_hint.setText(UI.list_hint)
        self.list_hint.setVisible(True)

    def _refresh_mid_state(self) -> None:
        has_selection = self.selected_index is not None and 0 <= int(self.selected_index) < len(self.filtered_indices)
        self._session_panel.refresh_mid_state(
            is_scanning=bool(self.is_scanning),
            is_connecting=bool(self.is_connecting),
            is_connected=bool(self.is_connected),
            cars_present=bool(self.cars),
            has_selection=bool(has_selection),
        )

    def _show_video_requirements_hint(self) -> None:
        self._show_banner(
            "muted",
            (
                "Embedded video requires GI/GStreamer. On Ubuntu/WSL: "
                "sudo apt install -y python3-gi gstreamer1.0-plugins-base gstreamer1.0-plugins-good"
            ),
            auto_hide_ms=12_000,
        )

    def _on_video_overlay_action_clicked(self) -> None:
        # Action is dynamic: either show requirements or retry.
        if self._video_missing_deps:
            self._show_video_requirements_hint()
            return
        if self._video_port_last is None:
            return
        if not self.is_connected:
            return
        self._start_video_for_car({"video_port": int(self._video_port_last)})

    def _refresh_video_overlay(self) -> None:
        # Drive Mode guard: when disconnected, the drive guard owns the screen.
        # Never allow placeholder text to reappear under the translucent overlay due to later ticks.
        try:
            if self.btn_drive.isChecked() and (not bool(self.is_connected)):
                self.video_view.setVisible(False)
                self.video_overlay.setVisible(False)
                return
        except Exception:
            pass

        # Overlay is visible when we don't have a pixmap/frame to show.
        if not self.is_connected:
            if self.is_connecting:
                self.video_overlay_title.setText(UI.overlay_title_video)
                self.video_overlay_body.setText(UI.overlay_connecting)
                self.video_overlay_action.setVisible(False)
                self.video_overlay.setVisible(True)
                # Prevent underlying placeholder text from bleeding through the overlay.
                self.video_view.setVisible(False)
                return
            if self.is_scanning:
                self.video_overlay_title.setText(UI.overlay_title_video)
                self.video_overlay_body.setText(UI.overlay_waiting_connection)
                self.video_overlay_action.setVisible(False)
                self.video_overlay.setVisible(True)
                self.video_view.setVisible(False)
                return
            self.video_overlay_title.setText(UI.overlay_title_video)
            self.video_overlay_body.setText(UI.overlay_no_active_session)
            self.video_overlay_action.setVisible(False)
            self.video_overlay.setVisible(True)
            self.video_view.setVisible(False)
            return

        if self.is_connecting:
            self.video_overlay_title.setText(UI.overlay_title_video)
            self.video_overlay_body.setText(UI.overlay_connecting)
            self.video_overlay_action.setVisible(False)
            self.video_overlay.setVisible(True)
            self.video_view.setVisible(False)
            return

        # Connected: show overlay only if we don't have a last pixmap.
        has_frame = self._last_video_pixmap is not None and (not self._last_video_pixmap.isNull())
        if has_frame:
            self.video_overlay.setVisible(False)
            self.video_view.setVisible(True)
            return

        self.video_overlay_title.setText(UI.overlay_video_not_available)
        if self._video_missing_deps:
            self.video_overlay_body.setText(UI.overlay_missing_deps)
            self.video_overlay_action.setText(UI.video_requirements_button)
            self.video_overlay_action.setVisible(True)
        else:
            self.video_overlay_body.setText(UI.overlay_no_frames)
            self.video_overlay_action.setText(UI.overlay_retry)
            self.video_overlay_action.setVisible(True)
        self.video_overlay.setVisible(True)
        self.video_view.setVisible(False)

    def _show_banner(self, kind: str, text: str, *, auto_hide_ms: int = 5000) -> None:
        msg = str(text)
        self._banner_token += 1
        token = int(self._banner_token)

        if self.banner.property("bannerKind") != kind:
            self.banner.setProperty("bannerKind", kind)
            self.banner.style().unpolish(self.banner)
            self.banner.style().polish(self.banner)
        if self.banner_text.text() != msg:
            self.banner_text.setText(msg)
        if not self.banner.isVisible():
            self.banner.setVisible(True)

        # Also mirror in Drive Mode where the header banner is hidden.
        if self.drive_banner.property("bannerKind") != kind:
            self.drive_banner.setProperty("bannerKind", kind)
            self.drive_banner.style().unpolish(self.drive_banner)
            self.drive_banner.style().polish(self.drive_banner)
        if self.drive_banner_text.text() != msg:
            self.drive_banner_text.setText(msg)
        # Drive banner must be visible in Drive layout, even if Drive is windowed (Wayland/WSLg).
        want_drive_visible = bool(self.btn_drive.isChecked())
        if self.drive_banner.isVisible() != want_drive_visible:
            self.drive_banner.setVisible(want_drive_visible)
        try:
            if want_drive_visible:
                self.drive_banner.raise_()
                self.hud.raise_()
                self.btn_overlay_disconnect.raise_()
        except Exception:
            pass

        # Drive Mode: auto-fade banners quickly unless danger.
        if want_drive_visible:
            drive_hide_ms = 0
            if kind != "danger":
                drive_hide_ms = 3000
            elif auto_hide_ms > 0:
                drive_hide_ms = auto_hide_ms
            if drive_hide_ms > 0:
                QTimer.singleShot(
                    drive_hide_ms,
                    lambda t=token: self._hide_banner() if int(self._banner_token) == int(t) else None,
                )
        else:
            if auto_hide_ms > 0:
                QTimer.singleShot(
                    auto_hide_ms,
                    lambda t=token: self._hide_banner() if int(self._banner_token) == int(t) else None,
                )

    def _hide_banner(self) -> None:
        self.banner.setVisible(False)
        self.drive_banner.setVisible(False)
        self._cancel_autoconnect()

    def _cancel_autoconnect(self) -> None:
        self._autoconnect_seq += 1
        self._autoconnect_pending = False

    def _schedule_autoconnect(self, car: Car) -> None:
        if bool(self.is_connected or self.is_connecting):
            return
        if bool(getattr(self.controller, "stop_event", None) is not None):
            return
        self._autoconnect_seq += 1
        seq = int(self._autoconnect_seq)
        self._autoconnect_pending = True

        self._show_banner(
            "muted",
            UI.auto_connecting_single.format(name=car.name, ip=car.ip, port=car.control_port),
            auto_hide_ms=0,
        )

        delay_ms = int(getattr(self.cfg, "auto_connect_delay_ms", 1200))
        delay_ms = 0 if delay_ms < 0 else min(delay_ms, 10_000)

        def _connect_if_latest() -> None:
            if seq != self._autoconnect_seq:
                return
            self._autoconnect_pending = False
            self.connect_selected()

        QTimer.singleShot(delay_ms, _connect_if_latest)

    # ---------------- UI helpers ----------------
    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def focus_log_filter(self) -> None:
        self.log_filter.setFocus()
        self.log_filter.selectAll()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Exit app confirmation.
        if event.key() == Qt.Key_Q and (event.modifiers() & Qt.ControlModifier):
            self.close()
            event.accept()
            return
        if event.key() == Qt.Key_Escape and (event.modifiers() & Qt.ShiftModifier):
            self.close()
            event.accept()
            return

        # Enter to connect (operator UX). Avoid triggering while typing in text inputs.
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() == Qt.NoModifier:
            try:
                fw = self.focusWidget()
                if fw in (self.search, self.log_filter):
                    super().keyPressEvent(event)
                    return
            except Exception:
                pass
            try:
                self.connect_selected()
                event.accept()
                return
            except Exception:
                pass

        if event.key() == Qt.Key_Escape and self._autoconnect_pending:
            self._hide_banner()
            event.accept()
            return

        # Esc cancels scan when scanning (consistent with Scan=Cancel).
        if event.key() == Qt.Key_Escape and event.modifiers() == Qt.NoModifier:
            if self.is_scanning and (not self.is_connected) and (not self.btn_drive.isChecked()):
                self.cancel_scan()
                event.accept()
                return

        # Emergency exit from frameless/fullscreen scenarios.
        if event.key() == Qt.Key_Escape and (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)) == (
            Qt.ControlModifier | Qt.ShiftModifier
        ):
            self.apply_layout("A")
            event.accept()
            return

        # Fullscreen toggle for operators (works in any layout, including frameless Drive Mode).
        if event.key() == Qt.Key_F11:
            if self._is_wayland():
                # Wayland/WSLg is fragile with fullscreen transitions; ignore.
                event.accept()
                return
            if self.isFullScreen():
                # If we're in Drive Mode, also exit Drive layout back to Panel.
                if self.btn_drive.isChecked():
                    self.apply_layout("A")
                else:
                    self._run_when_window_has_size(self.showNormal)
                    self._update_bottom_hint()
            else:
                self._run_when_window_has_size(self.showFullScreen)
                self._update_bottom_hint()
            event.accept()
            return

        if event.key() == Qt.Key_Escape:
            # Priority:
            # 1) Drive Mode (B): return to Panel (A), do NOT disconnect.
            # Drive may be fullscreen (X11) or windowed (Wayland), so key off the layout toggle.
            if self.btn_drive.isChecked():
                self.apply_layout("A")
                event.accept()
                return
            # 2) Panel/other: if session is active -> disconnect
            if self.is_connected:
                self.disconnect_session()
                event.accept()
                return
            # 3) No session: Esc should NOT change window size/state.
            # Allow Esc to EXIT fullscreen, but never ENTER it.
            if self.isFullScreen():
                if self._is_wayland():
                    event.accept()
                    return
                self._run_when_window_has_size(self.showNormal)
                self._update_bottom_hint()
                event.accept()
                return
        super().keyPressEvent(event)

    # ---------------- Video (embedded, best-effort) ----------------
    def _start_video_for_car(self, car: Car | dict) -> None:
        if isinstance(car, Car):
            video_port = int(car.video_port)
        else:
            video_port = int(car.get("video_port", 5600))
        self._video_port_last = int(video_port)
        self._stop_video()
        self._video_missing_deps = False

        self.badge_video.setText(UI.badge_video_on)
        self._set_badge_kind(self.badge_video, "accent")
        self.hud_video.setText(UI.badge_video_on)
        self._set_badge_kind(self.hud_video, "accent")
        self.video_view.setText(UI.video_connecting)
        self.video_view.setPixmap(QPixmap())
        self.video_view.setScaledContents(False)
        self._video_retry_enabled = True

        def on_frame(frame: VideoFrame) -> None:
            # Called from GI thread context -> marshal to Qt thread.
            def _apply() -> None:
                img = QImage(frame.rgb_bytes, frame.width, frame.height, QImage.Format_BGRA8888)
                pix = QPixmap.fromImage(img)
                if self.video_view.width() > 10 and self.video_view.height() > 10:
                    pix = pix.scaled(self.video_view.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
                self._last_video_pixmap = pix
                self.video_view.setPixmap(pix)
                self.video_view.setScaledContents(False)
                self.btn_video_help.setVisible(False)
                self.video_overlay.setVisible(False)

            QTimer.singleShot(0, _apply)

        def on_error(msg: str) -> None:
            def _apply_err() -> None:
                self._append_log_rate_limited("WARN", msg, key="video-error", min_interval_ms=2500)
                self.video_view.setText(UI.video_not_available)
                self.badge_video.setText(UI.badge_video_off)
                self._set_badge_kind(self.badge_video, "muted")
                self.hud_video.setText(UI.badge_video_off)
                self._set_badge_kind(self.hud_video, "muted")
                self.video_view.setPixmap(QPixmap())
                # Show requirements only when GI/GStreamer is missing.
                lowered = str(msg).lower()
                missing_deps = ("gstreamer not available" in lowered) or ("gi/gstreamer" in lowered)
                self._video_missing_deps = bool(missing_deps)
                self.btn_video_help.setVisible(bool(missing_deps))
                # If GI/GStreamer is missing, retries are pointless.
                if missing_deps:
                    self._video_retry_enabled = False
                    self._append_log_rate_limited(
                        "INFO",
                        UI.video_deps_hint,
                        key="video-deps-hint",
                        min_interval_ms=30_000,
                    )
                    return
                self._schedule_video_retry(video_port)
                self._refresh_video_overlay()

            QTimer.singleShot(0, _apply_err)

        if self._video_receiver_factory is None:
            on_error(UI.video_backend_not_configured)
            return

        self._video_receiver = self._video_receiver_factory(
            port=video_port,
            latency_ms=self.cfg.video_latency_ms,
            on_frame=on_frame,
            on_error=on_error,
        )
        ok = self._video_receiver.start()
        if not ok:
            on_error(UI.video_backend_not_available)

    def _stop_video(self) -> None:
        if self._video_receiver is not None:
            try:
                self._video_receiver.stop()
            except Exception:
                pass
        self._video_receiver = None
        self._video_retry_ms = 500
        self._video_retry_enabled = True
        self._video_missing_deps = False
        self.video_view.setText(UI.video_not_available)
        self.video_view.setPixmap(QPixmap())
        self._last_video_pixmap = None
        self.btn_video_help.setVisible(False)
        self._refresh_video_overlay()
        self._set_badge_kind(self.badge_video, "muted")
        self.badge_video.setText(UI.badge_video_off)
        self.hud_video.setText(UI.badge_video_off)
        self._set_badge_kind(self.hud_video, "muted")

    def _resize_video_pixmap(self) -> None:
        # Keep aspect ratio on window/fullscreen resize even if frames pause.
        if self._last_video_pixmap is None or self._last_video_pixmap.isNull():
            return
        pix = self._last_video_pixmap
        if self.video_view.width() > 10 and self.video_view.height() > 10:
            pix = pix.scaled(self.video_view.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.video_view.setPixmap(pix)

    def _schedule_video_retry(self, video_port: int) -> None:
        if not self.is_connected:
            return
        if not self._video_retry_enabled:
            return
        delay = self._video_retry_ms
        self._video_retry_ms = min(self._video_retry_ms * 2, 5000)

        def _retry() -> None:
            if not self.is_connected:
                return
            # best-effort retry: just re-create receiver
            self._start_video_for_car({"video_port": video_port})

        QTimer.singleShot(delay, _retry)

    # ---------------- Rate-limited logging ----------------
    def _append_log_rate_limited(self, level: str, text: str, *, key: str, min_interval_ms: int) -> None:
        t_ms = int(time.time() * 1000)
        if key == "video-error":
            if self._video_last_error == text and (t_ms - self._video_last_error_ts_ms) < min_interval_ms:
                return
            self._video_last_error = text
            self._video_last_error_ts_ms = t_ms
        else:
            # generic: use last error slots too (good enough for this UI)
            if self._video_last_error == f"{key}:{text}" and (t_ms - self._video_last_error_ts_ms) < min_interval_ms:
                return
            self._video_last_error = f"{key}:{text}"
            self._video_last_error_ts_ms = t_ms

        self.append_log(level, text)

    # ---------------- Window state persistence ----------------
    def _restore_window_state(self) -> None:
        if self.settings is None:
            return
        try:
            geom = self.settings.value("qt/geometry")
            if geom is not None:
                ok = self.restoreGeometry(geom)
                # If persisted geometry is corrupted/unusable, fall back to a sane default
                # and clear the persisted value so we don't crash-loop on Wayland/WSLg.
                if not ok:
                    self.resize(1280, 800)
                    self.settings.setValue("qt/geometry", None)
            # Wayland/WSLg: restoreState() can trigger maximized/fullscreen 0x0 protocol errors.
            # Geometry is usually safe; windowState is not.
            if not self._is_wayland():
                state = self.settings.value("qt/windowState")
                if state is not None:
                    ok2 = self.restoreState(state)
                    if not ok2:
                        self.settings.setValue("qt/windowState", None)
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        # Premium UX: always confirm exit (predictable), and tailor copy when risky.
        if not self._closing:
            try:
                drive_alive = self.controller.drive_thread is not None and self.controller.drive_thread.is_alive()
                scan_alive = self.controller.scan_thread is not None and self.controller.scan_thread.is_alive()
                risky = bool(self.is_connected or self.is_connecting or self.is_scanning or drive_alive or scan_alive)
            except Exception:
                risky = True

            box = QMessageBox(self)
            # Keep visual chrome consistent with the app (frameless).
            try:
                box.setWindowFlag(Qt.FramelessWindowHint, True)
            except Exception:
                pass
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(UI.exit_confirm_title)
            box.setText(UI.exit_confirm_body if risky else UI.exit_confirm_body_idle)
            btn_exit = box.addButton(UI.exit_confirm_exit, QMessageBox.ButtonRole.AcceptRole)
            box.addButton(UI.exit_confirm_cancel, QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_exit)
            box.exec()
            if box.clickedButton() is not btn_exit:
                event.ignore()
                return
            self._closing = True

        # Stop premium timers first to avoid transitions/pulses during shutdown.
        try:
            if self._pulse_timer is not None and self._pulse_timer.isActive():
                self._pulse_timer.stop()
        except Exception:
            pass

        try:
            self.timer.stop()
        except Exception:
            pass

        if risky:
            try:
                # Micro-overlay: "Stopping system..." (helps operator confidence on close).
                if self._shutdown_overlay is None:
                    self._shutdown_overlay = QWidget(self)
                    self._shutdown_overlay.setObjectName("fadeOverlay")
                    overlay_layout = QVBoxLayout(self._shutdown_overlay)
                    overlay_layout.setContentsMargins(16, 16, 16, 16)
                    overlay_layout.addStretch(1)
                    msg = QLabel("Stopping system…", self._shutdown_overlay)
                    msg.setProperty("badge", True)
                    msg.setProperty("badgeKind", "muted")
                    msg.setAlignment(Qt.AlignHCenter)
                    overlay_layout.addWidget(msg, 0, alignment=Qt.AlignHCenter)
                    overlay_layout.addStretch(1)
                self._shutdown_overlay.setGeometry(0, 0, self.width(), self.height())
                self._shutdown_overlay.show()
                self._shutdown_overlay.raise_()
                try:
                    from PySide6.QtWidgets import QApplication

                    QApplication.processEvents()
                except Exception:
                    pass
            except Exception:
                pass

        try:
            # Stop video first to prevent late callbacks/log noise during shutdown.
            self._stop_video()
        except Exception:
            pass

        try:
            # Signal background work to stop.
            self.controller.shutdown()
        except Exception:
            pass

        if risky:
            # Deterministic teardown: block briefly to join threads (best-effort).
            try:
                t_drive = self.controller.drive_thread
                if t_drive is not None and t_drive.is_alive():
                    t_drive.join(timeout=0.5)
            except Exception:
                pass
            try:
                t_scan = self.controller.scan_thread
                if t_scan is not None and t_scan.is_alive():
                    t_scan.join(timeout=0.5)
            except Exception:
                pass

        try:
            # Avoid persisting Drive Mode as the default layout.
            if self.settings is not None:
                if str(self.settings.value("layout_id", "A")) == "B":
                    self.settings.setValue("layout_id", "A")
                # Never persist invalid 0x0 geometry (can crash-loop Wayland).
                if self.width() > 0 and self.height() > 0:
                    self.settings.setValue("qt/geometry", self.saveGeometry())
                    if not self._is_wayland():
                        self.settings.setValue("qt/windowState", self.saveState())
                try:
                    self._save_left_splitter_sizes()
                except Exception:
                    pass
        except Exception:
            pass
        super().closeEvent(event)

    def _restore_left_splitter_sizes(self) -> None:
        if self.settings is None:
            return
        raw = self.settings.value("ui/leftSplitterSizes")
        if not raw:
            return
        sizes: list[int] = []
        if isinstance(raw, (list, tuple)):
            for x in raw:
                try:
                    sizes.append(int(x))
                except Exception:
                    pass
        else:
            try:
                parts = [p.strip() for p in str(raw).replace(";", ",").split(",") if p.strip()]
                sizes = [int(p) for p in parts]
            except Exception:
                sizes = []
        if len(sizes) >= 2 and all(s > 0 for s in sizes[:2]):
            self.left_splitter.setSizes([int(sizes[0]), int(sizes[1])])

    def _schedule_save_left_splitter_sizes(self) -> None:
        if self._splitter_save_timer is None:
            self._splitter_save_timer = QTimer(self)
            self._splitter_save_timer.setSingleShot(True)
            self._splitter_save_timer.timeout.connect(self._save_left_splitter_sizes)
        self._splitter_save_timer.start(250)

    def _save_left_splitter_sizes(self) -> None:
        if self.settings is None:
            return
        try:
            sizes = self.left_splitter.sizes()
        except Exception:
            return
        if not sizes or len(sizes) < 2:
            return
        a, b = int(sizes[0]), int(sizes[1])
        if a <= 0 or b <= 0:
            return
        self.settings.setValue("ui/leftSplitterSizes", [a, b])

    # ---------------- Cars list ----------------
    def apply_car_filter(self) -> None:
        self._cars_panel.apply_car_filter()

    def _refresh_car_row_active_styles(self) -> None:
        self._cars_panel.refresh_car_row_active_styles()

    def _debounce_apply_car_filter(self) -> None:
        self._cars_panel.debounce_apply_car_filter()

    def on_select(self) -> None:
        self._cars_panel.on_select()
        # Persist last selected car (best-effort) for next scan/session.
        if self.settings is None:
            return
        if self.selected_index is None:
            return
        if not (0 <= int(self.selected_index) < len(self.filtered_indices)):
            return
        try:
            car = self.cars[self.filtered_indices[int(self.selected_index)]]
            ip = str(getattr(car, "ip", "") or "").strip()
            if ip:
                self.settings.setValue("ui/lastSelectedCarIp", ip)
        except Exception:
            pass

    # ---------------- Logs ----------------
    def append_log(self, level: str, text: str) -> None:
        self._log_panel.append_log(level, text)

    def clear_log(self) -> None:
        self._log_panel.clear_log()

    def refresh_log_view(self) -> None:
        self._log_panel.refresh_log_view()

    def _on_pause_log_toggled(self, paused: bool) -> None:
        self._log_panel.on_pause_toggled(paused)

    def _on_log_scroll_changed(self) -> None:
        # (Kept for compatibility; actual scroll handling lives in LogPanel.)
        self._log_panel._on_log_scroll_changed()

    # ---------------- Queue draining ----------------
    def process_ui_queue(self) -> None:
        max_items = int(getattr(self.cfg, "max_events_per_tick", 200))
        drained = drain_queue(self.ui_queue, max_items=max_items)

        # Telemetry flood guard: coalesce to the latest payload per tick.
        last_telemetry_payload: dict | None = None
        for ev in drained:
            match ev:
                case StatusEvent(summary=summary, detail=detail, phase=phase):
                    if summary:
                        self.session_label.setText(f"{UI.session_status_prefix}{summary}")
                    self.detail_label.setText(detail)
                    if phase is not None:
                        try:
                            self.phase = phase
                        except Exception:
                            pass
                        try:
                            self._apply_primary_state_badge(phase)
                        except Exception:
                            pass
                        # Derive UI booleans from phase (single source of truth).
                        is_scanning, is_connecting, should_set_connected, should_set_disconnected = (
                            self._session_panel.derive_flags_from_phase(
                                phase=phase, was_connected=bool(self.is_connected)
                            )
                        )
                        self.is_scanning = bool(is_scanning)
                        self.is_connecting = bool(is_connecting)
                        if should_set_connected:
                            self.set_connection_state(True)
                        if should_set_disconnected:
                            self.set_connection_state(False)
                case TelemetryEvent(payload=payload):
                    if isinstance(payload, dict):
                        last_telemetry_payload = payload
                case LogEvent(level=level, message=message):
                    self.append_log(str(level), str(message))
                case CarsEvent(cars=cars):
                    self.cars = list(cars) if isinstance(cars, list) else []
                    self.apply_car_filter()
                    if self.cars:
                        try:
                            self.list.setFocus()
                        except Exception:
                            pass
                    self._update_left_hint()
                    if self.cars:
                        self.append_log("INFO", UI.scan_complete_found.format(count=len(self.cars)))
                        if (
                            len(self.cars) == 1
                            and bool(getattr(self.cfg, "auto_connect_single", True))
                            and (not self.is_connected)
                            and (not self.is_connecting)
                        ):
                            self.selected_index = 0
                            self._schedule_autoconnect(self.cars[0])
                    else:
                        self.append_log("WARN", UI.scan_complete_none)
                case ScanDoneEvent():
                    self.is_scanning = False
                    if not self.is_connected and not self.is_connecting:
                        self._apply_primary_state_badge(AppPhase.IDLE)
                    # If we were only scanning (not connected), ensure the session label
                    # returns to a stable idle state instead of staying on "Scanning…".
                    if not self.is_connected and not self.is_connecting:
                        self.session_label.setText(f"{UI.session_status_prefix}{UI.badge_disconnected}")
                        self.detail_label.setText("")
                    self._update_left_hint()
                    self._update_controls()
                case ErrorEvent(message=message):
                    self.append_log("ERROR", str(message))
                    self._show_banner("danger", f"{UI.error_prefix}{message}", auto_hide_ms=8000)
                case MozaStateEvent(connected=ok):
                    self.badge_moza.setText(format_moza_badge(state="ok" if ok else "no"))
                    self._set_badge_kind(self.badge_moza, "ok" if ok else "warn")
                    self.hud_moza.setText(format_moza_badge(state="ok" if ok else "no"))
                    self._set_badge_kind(self.hud_moza, "ok" if ok else "warn")
                case SessionStoppedEvent():
                    self.append_log("WARN", UI.session_ended)
                    self.set_connection_state(False)
                    self._stop_video()
                    self.badge_video.setText(UI.badge_video_off)
                    self._set_badge_kind(self.badge_video, "muted")
                    self.badge_moza.setText(format_moza_badge(state="unknown"))
                    self._set_badge_kind(self.badge_moza, "muted")
                    self.active_car_id = None
                    self._refresh_car_row_active_styles()
                    self.is_connecting = False
                    self._update_controls()
                case _:
                    # Unknown event: ignore for forward-compat.
                    pass

        if last_telemetry_payload is not None:
            payload = last_telemetry_payload
            self.telemetry_label.setText(str(payload.get("text", "")))
            out = payload.get("output")
            if out is not None:
                try:
                    self.badge_output.setText(f"{float(out):+0.3f}")
                except Exception:
                    pass
            self._update_debug_telemetry(payload)

    def _set_badge_kind(self, badge: QLabel, kind: str) -> None:
        did_change = False
        if badge.property("badge") is not True:
            badge.setProperty("badge", True)
            did_change = True
        if badge.property("badgeKind") != kind:
            badge.setProperty("badgeKind", kind)
            did_change = True
        if did_change:
            badge.style().unpolish(badge)
            badge.style().polish(badge)
        # HUD dimming via QSS can be added later if needed; keep rendering simple here.

    def resizeEvent(self, event) -> None:
        try:
            if self._fade_overlay is not None:
                # Cover the whole window, including docks.
                self._fade_overlay.setGeometry(0, 0, self.width(), self.height())
        except Exception:
            pass
        try:
            self._resize_video_pixmap()
        except Exception:
            pass
        super().resizeEvent(event)

    def _set_pulse(self, widget: QWidget, on: bool) -> None:
        want = bool(on)
        if bool(widget.property("pulse")) == want:
            return
        widget.setProperty("pulse", want)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _refresh_pulse_state(self) -> None:
        active = bool(self.is_scanning or self.is_connecting)
        if not active:
            self._pulse_on = False
            try:
                self._set_pulse(self.mid_state, False)
                self._set_pulse(self.badge_conn, False)
            except Exception:
                pass
            if self._pulse_timer is not None and self._pulse_timer.isActive():
                self._pulse_timer.stop()
            return

        if self._pulse_timer is not None and not self._pulse_timer.isActive():
            self._pulse_timer.start()

    def _on_pulse_tick(self) -> None:
        if not (self.is_scanning or self.is_connecting):
            self._refresh_pulse_state()
            return
        self._pulse_on = not self._pulse_on
        try:
            self._set_pulse(self.mid_state, self._pulse_on)
            self._set_pulse(self.badge_conn, self._pulse_on)
        except Exception:
            pass

    def _update_debug_telemetry(self, payload: dict) -> None:
        self._last_telemetry = payload
        self._telemetry_trace.append(payload)
        if len(self._telemetry_trace) > 50:
            self._telemetry_trace = self._telemetry_trace[-50:]

        def _clamp01(x: float) -> float:
            return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

        try:
            steer = float(payload.get("steer", 0.0))
            gas = float(payload.get("gas", 0.0))
            brake = float(payload.get("brake", 0.0))
            out = float(payload.get("output", 0.0))
        except Exception:
            return

        self.t_out.setText(f"Output: {out:+0.3f}")
        self.hud_output.setText(f"{out:+0.3f}")
        self._set_badge_kind(self.hud_output, "accent")
        self._steer_bar.setValue(int(_clamp01(abs(steer)) * 1000))
        self._gas_bar.setValue(int(_clamp01(gas) * 1000))
        self._brake_bar.setValue(int(_clamp01(brake) * 1000))

        # raw view (compact)
        keys = ["steer", "gas", "brake", "output", "text"]
        lines = []
        for k in keys:
            if k in payload:
                lines.append(f"{k}: {payload.get(k)}")
        self.telemetry_raw.setPlainText("\n".join(lines))

        # trace view (last N)
        trace_lines = []
        for row in self._telemetry_trace[-12:]:
            try:
                trace_lines.append(
                    f"steer={float(row.get('steer', 0.0)):+0.3f}  "
                    f"gas={float(row.get('gas', 0.0)):.3f}  "
                    f"brake={float(row.get('brake', 0.0)):.3f}  "
                    f"out={float(row.get('output', 0.0)):+0.3f}"
                )
            except Exception:
                trace_lines.append(str(row))
        self.trace_view.setPlainText("\n".join(trace_lines))
