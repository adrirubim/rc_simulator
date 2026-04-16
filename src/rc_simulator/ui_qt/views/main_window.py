from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata

from PySide6.QtCore import QEasingCurve, QEvent, QEventLoop, QPoint, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QGuiApplication, QImage, QKeyEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGraphicsOpacityEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...app.ports import SessionControllerPort
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
from ...ports.video import VideoError, VideoErrorCode, VideoFrame, VideoReceiver, VideoReceiverFactory
from ..components.banner import build_banner
from ..components.docks import build_debug_docks, build_log_panel
from ..components.header import build_header
from ..components.hud import build_hud, format_moza_badge
from ..strings import UI, UiStrings, get_ui_strings, normalize_ui_language, set_ui_language
from ..styles.theme_qss import build_qss
from ._cars_panel import CarsPanel
from ._drive_surface import (
    ensure_layout_roots_visible as _ensure_layout_roots_visible,
)
from ._drive_surface import (
    mount_video_into_dashboard as _mount_video_into_dashboard,
)
from ._drive_surface import (
    mount_video_into_drive_root as _mount_video_into_drive_root,
)
from ._layout_manager import (
    apply_layout as _apply_layout_mgr,
)
from ._layout_manager import (
    apply_layout_now_impl as _apply_layout_now_impl_mgr,
)
from ._layout_manager import (
    force_end_layout_transition_if_stuck as _force_end_layout_transition_if_stuck_mgr,
)
from ._layout_manager import (
    on_layout_fade_in_done as _on_layout_fade_in_done_mgr,
)
from ._log_panel import LogPanel
from ._queue_drain import drain_queue
from ._session_panel import SessionPanel


@dataclass
class CarRow:
    name: str
    ip: str
    control_port: int
    video_port: int


class MainWindow(QMainWindow):
    """
    Main Qt window (presentation layer).

    Gold Master behavior highlights:
    - UI drains a bounded UiEvent queue and coalesces high-frequency telemetry/log bursts per tick
      to keep the GUI responsive under load.
    - Video frames are rendered as BGRA8888 (`QImage.Format_BGRA8888`) via the `VideoReceiver` port.
    - Layout transitions use a subtle "fade-to-obsidian" overlay (`#fadeOverlay`).
    - MOZA connection state is surfaced with stable `◆/◇` glyphs (zero-jump indicator).
    """

    SETTINGS_KEY_UI_LANGUAGE = "ui/language"

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

        # UI language (runtime switchable, persisted).
        self._ui_language: str = self._read_ui_language()
        # Set global UI proxy before building widgets that reference `UI.*`.
        self._ui: UiStrings = set_ui_language(self._ui_language)

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
        self._video_retry_profile: str = "stable"
        self._video_retry_seq: int = 0

        self._last_telemetry: dict = {}
        self._telemetry_trace: list[dict] = []
        self._autoconnect_seq: int = 0
        self._autoconnect_pending: bool = False

        # Session elapsed time badge (center header instruments).
        self._session_started_mono: float | None = None

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
        self._exit_confirm_overlay: QWidget | None = None
        self._exit_confirm_card: QWidget | None = None
        self._exit_confirm_effect: QGraphicsOpacityEffect | None = None
        self._exit_confirm_anim: QVariantAnimation | None = None
        self._exit_confirm_title: QLabel | None = None
        self._exit_confirm_body: QLabel | None = None
        self._exit_confirm_btn_cancel: QPushButton | None = None
        self._exit_confirm_btn_exit: QPushButton | None = None
        self._exit_confirm_finish: Callable[[bool], None] | None = None
        # Toast overlay (non-reflow notifications under header).
        self._toast_overlay: QWidget | None = None
        self._toast_effect: QGraphicsOpacityEffect | None = None
        self._toast_anim: QVariantAnimation | None = None
        self._toast_anchor: QPoint | None = None
        self._toast_last_msg: str = ""
        self._toast_last_kind: str = ""
        self._toast_last_ts_ms: int = 0

        self.setWindowTitle(UI.app_title)
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

        # Startup fullscreen:
        # - If we start in Drive (layout B), we always request fullscreen to hide OS chrome.
        # - Otherwise, respect the stored user preference.
        # Avoid Wayland/WSLg transitions here (Drive will handle best-effort fullscreen/maximize).
        try:
            start_in_drive = str(getattr(self, "_startup_layout_id", "A") or "A") == "B"
            if self.settings is not None:
                want_fs = bool(
                    int(
                        self.settings.value(
                            "ui/start_fullscreen",
                            1 if bool(getattr(self.cfg, "start_fullscreen", False)) else 0,
                        )
                        or 0
                    )
                )
            else:
                want_fs = bool(getattr(self.cfg, "start_fullscreen", False))
            if (start_in_drive or want_fs) and (not self._is_wayland()):
                self._run_when_window_has_size(self.showFullScreen)
        except Exception:
            pass

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
            import os

            platform = str(QGuiApplication.platformName() or "").lower()
            if "wayland" in platform:
                return True
            # Fallbacks: more reliable on WSLg/Wayland when Qt platformName is ambiguous.
            if str(os.environ.get("XDG_SESSION_TYPE", "") or "").lower() == "wayland":
                return True
            if os.environ.get("WAYLAND_DISPLAY"):
                return True
            return False
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

    def _mount_video_into_drive_root(self) -> None:
        _mount_video_into_drive_root(self)

    def _mount_video_into_dashboard(self) -> None:
        _mount_video_into_dashboard(self)

    def _ensure_layout_roots_visible(self) -> None:
        _ensure_layout_roots_visible(self)

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
        self._root_layout = root_layout
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
            on_toggle_settings_mode=self.toggle_settings_mode,
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
        self.badge_time = header.badge_time
        self.btn_drive = header.btn_drive
        self.btn_debug = header.btn_debug
        self.btn_settings = header.btn_settings
        self.btn_win_min = header.btn_min
        self.btn_win_max = header.btn_max
        self.btn_win_close = header.btn_close

        # Icons (built-in, no extra deps)
        self.btn_drive.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_debug.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.btn_settings.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        try:
            self._sync_window_controls()
        except Exception:
            pass

        root_layout.addWidget(self.header_widget)

        # Toast overlay (premium, non-reflow). Parent it to the central widget so
        # coordinates match the content area on all platforms.
        self._toast_overlay = QWidget(root)
        self._toast_overlay.setObjectName("toastOverlay")
        self._toast_overlay.hide()

        header_banner = build_banner(parent=self._toast_overlay, on_close=self._hide_banner)
        self.banner = header_banner.widget
        self.banner_text = header_banner.text
        self.banner_close = header_banner.close_button
        self.banner.hide()

        # Center content: left panel + center placeholder. Right is dock (log)
        center = QWidget(root)
        self._dashboard_center = center
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
        # Keep the layout stable: reserve space and update text without toggling visibility,
        # avoiding reflow/jumps when Scan is pressed.
        try:
            fm = self.list_hint.fontMetrics()
            self.list_hint.setFixedHeight(int(fm.lineSpacing() * 2 + 6))
        except Exception:
            pass
        self.list_hint.setVisible(True)
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
        # Keep layout stable: keep progress row visible; SessionPanel will switch it between
        # indeterminate (busy) and empty (idle).
        self.phase_progress.setVisible(True)
        try:
            self.phase_progress.setProperty("busy", False)
        except Exception:
            pass

        self.telemetry_label = QLabel(UI.session_inactive, self.mid_panel)
        self.telemetry_label.setWordWrap(True)
        # Keep the video block stable: reserve space for dynamic status rows above "Live video".
        # Avoid toggling visibility (which causes layout reflow and shifts the video).
        try:
            fm = self.session_label.fontMetrics()
            self.session_label.setFixedHeight(int(fm.lineSpacing() + 4))
            # Detail label can wrap; reserve ~2 lines for long car names / i18n.
            self.detail_label.setWordWrap(True)
            self.detail_label.setFixedHeight(int(fm.lineSpacing() * 2 + 6))
        except Exception:
            try:
                self.detail_label.setWordWrap(True)
            except Exception:
                pass
        try:
            self.session_label.setVisible(True)
            self.detail_label.setVisible(True)
        except Exception:
            pass
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
        self.video_overlay_title = QLabel(UI.overlay_title_video, self.video_overlay)
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

        # Drive toast overlay: non-reflow alerts inside the video surface.
        self._drive_toast_overlay = QWidget(self.video_container)
        self._drive_toast_overlay.setObjectName("driveToastOverlay")
        self._drive_toast_overlay.hide()

        drive_banner = build_banner(parent=self._drive_toast_overlay, on_close=self._hide_banner)
        self.drive_banner = drive_banner.widget
        self.drive_banner_text = drive_banner.text
        self.drive_banner_close = drive_banner.close_button
        self.drive_banner.hide()

        mid_l.addWidget(self.video_container, 1)
        self.telemetry_caption = QLabel(UI.telemetry_label, self.mid_panel)
        mid_l.addWidget(self.telemetry_caption)
        mid_l.addWidget(self.telemetry_label)

        # Settings panel (Layout D)
        self.settings_panel = QWidget(self.mid_panel)
        self.settings_panel.setObjectName("settingsPanel")
        self.settings_panel.setProperty("card", True)
        sp_l = QVBoxLayout(self.settings_panel)
        sp_l.setContentsMargins(0, 0, 0, 0)
        sp_l.setSpacing(10 if self.cfg.density != "compact" else 8)

        self.settings_title = QLabel(UI.settings_title, self.settings_panel)
        self.settings_title.setObjectName("title")
        sp_l.addWidget(self.settings_title)

        # Scrollable content keeps Settings usable in small windows.
        settings_scroll = QScrollArea(self.settings_panel)
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        sp_l.addWidget(settings_scroll, 1)

        settings_content = QWidget(settings_scroll)
        settings_scroll.setWidget(settings_content)
        sc_l = QVBoxLayout(settings_content)
        sc_l.setContentsMargins(0, 0, 0, 0)
        sc_l.setSpacing(12 if self.cfg.density != "compact" else 10)

        # "Current status" is read-only and reflects effective runtime state.
        self.settings_status_box = QGroupBox(UI.settings_section_status, settings_content)
        status_form = QFormLayout(self.settings_status_box)
        status_form.setHorizontalSpacing(12)
        status_form.setVerticalSpacing(10)
        self.settings_status_layout_label = QLabel(UI.settings_status_layout, self.settings_status_box)
        self.settings_status_layout_value = QLabel("", self.settings_status_box)
        self.settings_status_phase_label = QLabel(UI.settings_status_phase, self.settings_status_box)
        self.settings_status_phase_value = QLabel("", self.settings_status_box)
        self.settings_status_fullscreen_label = QLabel(UI.settings_status_fullscreen, self.settings_status_box)
        self.settings_status_fullscreen_value = QLabel("", self.settings_status_box)
        self.settings_status_platform_label = QLabel(UI.settings_status_platform, self.settings_status_box)
        self.settings_status_platform_value = QLabel("", self.settings_status_box)
        for w in (
            self.settings_status_layout_value,
            self.settings_status_phase_value,
            self.settings_status_fullscreen_value,
            self.settings_status_platform_value,
        ):
            w.setObjectName("muted")
            w.setWordWrap(True)
        status_form.addRow(self.settings_status_layout_label, self.settings_status_layout_value)
        status_form.addRow(self.settings_status_phase_label, self.settings_status_phase_value)
        status_form.addRow(self.settings_status_fullscreen_label, self.settings_status_fullscreen_value)
        status_form.addRow(self.settings_status_platform_label, self.settings_status_platform_value)

        self.settings_display_box = QGroupBox(UI.settings_section_display, settings_content)
        display_form = QFormLayout(self.settings_display_box)
        display_form.setHorizontalSpacing(12)
        display_form.setVerticalSpacing(10)

        self.settings_behavior_box = QGroupBox(UI.settings_section_behavior, settings_content)
        behavior_form = QFormLayout(self.settings_behavior_box)
        behavior_form.setHorizontalSpacing(12)
        behavior_form.setVerticalSpacing(10)

        self.settings_video_box = QGroupBox(UI.settings_section_video, settings_content)
        video_form = QFormLayout(self.settings_video_box)
        video_form.setHorizontalSpacing(12)
        video_form.setVerticalSpacing(10)

        self.settings_logs_box = QGroupBox(UI.settings_section_logs, settings_content)
        logs_form = QFormLayout(self.settings_logs_box)
        logs_form.setHorizontalSpacing(12)
        logs_form.setVerticalSpacing(10)

        self.settings_theme = QComboBox(self.settings_display_box)
        self.settings_theme.clear()
        self.settings_theme.addItem(UI.settings_theme_slate, "slate")
        self.settings_theme.addItem(UI.settings_theme_glass, "glass")
        self.settings_theme.setToolTip(UI.settings_tooltip_theme)
        self.settings_density = QComboBox(self.settings_display_box)
        self.settings_density.clear()
        self.settings_density.addItem(UI.settings_density_normal, "normal")
        self.settings_density.addItem(UI.settings_density_compact, "compact")
        self.settings_density.setToolTip(UI.settings_tooltip_density)
        self.settings_auto_scan = QCheckBox(UI.settings_auto_scan, self.settings_behavior_box)
        self.settings_auto_scan.setToolTip(UI.settings_tooltip_auto_scan)
        self.settings_auto_connect_single = QCheckBox(UI.settings_auto_connect_single, self.settings_behavior_box)
        self.settings_auto_connect_single.setToolTip(UI.settings_tooltip_auto_connect_single)
        self.settings_start_fullscreen = QCheckBox(UI.settings_start_fullscreen, self.settings_behavior_box)
        self.settings_start_fullscreen.setToolTip(UI.settings_tooltip_start_fullscreen)
        self.settings_video_latency = QSpinBox(self.settings_video_box)
        self.settings_video_latency.setRange(0, 250)
        self.settings_video_latency.setSingleStep(10)
        self.settings_video_latency.setSuffix(" ms")
        self.settings_video_latency.setToolTip(UI.settings_tooltip_receiver_latency)

        self.settings_retry_profile = QComboBox(self.settings_video_box)
        self.settings_retry_profile.clear()
        self.settings_retry_profile.addItem(UI.settings_retry_stable, "stable")
        self.settings_retry_profile.addItem(UI.settings_retry_aggressive, "aggressive")
        self.settings_retry_profile.setToolTip(UI.settings_tooltip_retry_profile)

        self.settings_log_visible = QComboBox(self.settings_logs_box)
        self.settings_log_visible.addItems(["500", "2000", "5000"])
        self.settings_log_store = QComboBox(self.settings_logs_box)
        self.settings_log_store.addItems(["5000", "20000", "50000"])
        self.settings_log_visible.setToolTip(UI.settings_tooltip_visible_lines)
        self.settings_log_store.setToolTip(UI.settings_tooltip_stored_lines)

        self.settings_theme_label = QLabel(UI.settings_theme_label, self.settings_display_box)
        self.settings_density_label = QLabel(UI.settings_density_label, self.settings_display_box)
        display_form.addRow(self.settings_theme_label, self.settings_theme)
        display_form.addRow(self.settings_density_label, self.settings_density)

        self.settings_language_label = QLabel(UI.settings_language_label, self.settings_display_box)
        self.settings_language_row = QWidget(self.settings_display_box)
        lang_l = QHBoxLayout(self.settings_language_row)
        lang_l.setContentsMargins(0, 0, 0, 0)
        lang_l.setSpacing(8 if self.cfg.density == "compact" else 10)
        self.settings_language_group = QButtonGroup(self.settings_language_row)
        self.settings_language_group.setExclusive(True)
        self.settings_language_buttons: dict[str, QToolButton] = {}
        for code, text, tip in (("en", "EN", "English"), ("it", "IT", "Italiano"), ("es", "ES", "Español")):
            b = QToolButton(self.settings_language_row)
            b.setObjectName("langDot")
            b.setCheckable(True)
            b.setText(text)
            b.setToolTip(tip)
            b.setProperty("lang", code)
            b.clicked.connect(lambda _checked=False, c=code: self._set_ui_language(c))
            self.settings_language_group.addButton(b)
            self.settings_language_buttons[code] = b
            lang_l.addWidget(b)
        lang_l.addStretch(1)
        display_form.addRow(self.settings_language_label, self.settings_language_row)
        behavior_form.addRow("", self.settings_auto_scan)
        behavior_form.addRow("", self.settings_auto_connect_single)
        behavior_form.addRow("", self.settings_start_fullscreen)
        self.settings_receiver_latency_label = QLabel(UI.settings_receiver_latency_label, self.settings_video_box)
        self.settings_retry_profile_label = QLabel(UI.settings_retry_profile_label, self.settings_video_box)
        self.settings_visible_lines_label = QLabel(UI.settings_visible_lines_label, self.settings_logs_box)
        self.settings_stored_lines_label = QLabel(UI.settings_stored_lines_label, self.settings_logs_box)
        video_form.addRow(self.settings_receiver_latency_label, self.settings_video_latency)
        video_form.addRow(self.settings_retry_profile_label, self.settings_retry_profile)
        logs_form.addRow(self.settings_visible_lines_label, self.settings_log_visible)
        logs_form.addRow(self.settings_stored_lines_label, self.settings_log_store)

        sc_l.addWidget(self.settings_status_box)
        sc_l.addWidget(self.settings_display_box)
        sc_l.addWidget(self.settings_behavior_box)
        sc_l.addWidget(self.settings_video_box)
        sc_l.addWidget(self.settings_logs_box)
        sc_l.addStretch(1)

        btn_row = QWidget(self.settings_panel)
        btn_row_l = QHBoxLayout(btn_row)
        btn_row_l.setContentsMargins(0, 0, 0, 0)
        btn_row_l.addStretch(1)
        self.settings_copy_diag = QPushButton(UI.settings_copy_diagnostics, btn_row)
        self.settings_copy_diag.setObjectName("secondaryButton")
        self.settings_copy_diag.clicked.connect(self._copy_diagnostics)
        self.settings_copy_diag.setAccessibleName(UI.settings_copy_diag_accessible_name)
        self.settings_copy_diag.setAccessibleDescription(UI.settings_copy_diag_accessible_desc)
        btn_row_l.addWidget(self.settings_copy_diag)
        self.settings_apply = QPushButton(UI.settings_apply, btn_row)
        self.settings_apply.setObjectName("primaryButton")
        self.settings_apply.clicked.connect(self._apply_settings_from_ui)
        self.settings_apply.setAccessibleName(UI.settings_apply_accessible_name)
        self.settings_apply.setAccessibleDescription(UI.settings_apply_accessible_desc)
        btn_row_l.addWidget(self.settings_apply)
        sp_l.addWidget(btn_row)

        self.settings_panel.setVisible(False)
        mid_l.addWidget(self.settings_panel, 1)

        center_l.addWidget(self.mid_panel, 4)

        root_layout.addWidget(center, 1)

        # Dedicated Drive root: fullscreen canvas (video + overlays only).
        self.drive_root = QWidget(root)
        self.drive_root.setObjectName("driveRoot")
        dr_l = QVBoxLayout(self.drive_root)
        dr_l.setContentsMargins(0, 0, 0, 0)
        dr_l.setSpacing(0)
        self.drive_root.setVisible(False)
        root_layout.addWidget(self.drive_root, 1)
        # Remember where the video lives in the dashboard layout.
        self._mid_layout = mid_l
        self._video_dashboard_index = int(mid_l.indexOf(self.video_container))

        # Bottom status bar (simple label)
        self.bottom = QLabel("", root)
        self.bottom.setObjectName("muted")
        root_layout.addWidget(self.bottom)

        self.setCentralWidget(root)

        # Fade overlay (cinematic transitions).
        self._fade_overlay = QWidget(self)
        self._fade_overlay.setObjectName("fadeOverlay")
        self._fade_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._fade_overlay_effect = QGraphicsOpacityEffect(self._fade_overlay)
        self._fade_overlay_effect.setOpacity(0.0)
        self._fade_overlay.setGraphicsEffect(self._fade_overlay_effect)
        self._fade_overlay.hide()
        self._set_fade_overlay_alpha(0.0)

        log_panel = build_log_panel(
            parent=self.left_panel,
            on_filter_changed=self.refresh_log_view,
            on_pause_toggled=self._on_pause_log_toggled,
            on_clear_clicked=self.clear_log,
            on_toggle_collapsed=self.toggle_system_log_collapsed,
        )
        self.system_log_panel = log_panel.widget
        self.system_log_title = log_panel.title
        self.log_filter = log_panel.filter
        self.log_view = log_panel.view
        self.btn_pause_log = log_panel.pause_button
        self.btn_clear_log = log_panel.clear_button
        self.btn_collapse_log = log_panel.collapse_button
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
        # Restore collapsed state (dashboard cleanliness).
        try:
            if self.settings is not None:
                collapsed = bool(int(self.settings.value("ui/log_collapsed", 0) or 0))
                if collapsed:
                    self._set_system_log_collapsed(True)
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
            get_is_scanning=lambda: bool(self.is_scanning),
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
            on_after_filter_applied=self._render_state,
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

        self._render_state()
        try:
            self._sync_header_nav_buttons(
                str(self.settings.value("layout_id", "A")) if self.settings is not None else "A"
            )
        except Exception:
            pass

        # Settings UI defaults
        try:
            if self.settings is not None:
                theme = str(self.settings.value("ui/theme", getattr(self.cfg, "theme", "slate")) or "slate")
                density = str(self.settings.value("ui/density", getattr(self.cfg, "density", "normal")) or "normal")
                # Combos store internal values in itemData; select by data.
                theme_val = theme if theme in ("slate", "glass") else "slate"
                for i in range(self.settings_theme.count()):
                    if str(self.settings_theme.itemData(i) or "") == theme_val:
                        self.settings_theme.setCurrentIndex(i)
                        break
                density_val = density if density in ("normal", "compact") else "normal"
                for i in range(self.settings_density.count()):
                    if str(self.settings_density.itemData(i) or "") == density_val:
                        self.settings_density.setCurrentIndex(i)
                        break
                self.settings_auto_scan.setChecked(bool(int(self.settings.value("ui/auto_scan", 1) or 0)))
                self.settings_auto_connect_single.setChecked(
                    bool(int(self.settings.value("ui/auto_connect_single", 1) or 0))
                )
                self.settings_start_fullscreen.setChecked(
                    bool(
                        int(
                            self.settings.value(
                                "ui/start_fullscreen",
                                1 if bool(getattr(self.cfg, "start_fullscreen", False)) else 0,
                            )
                            or 0
                        )
                    )
                )
                try:
                    self.settings_video_latency.setValue(int(self.settings.value("video/latency_ms", 60) or 60))
                except Exception:
                    self.settings_video_latency.setValue(60)
                try:
                    retry = str(self.settings.value("video/retry_profile", "stable") or "stable")
                    retry_val = retry if retry in ("stable", "aggressive") else "stable"
                    for i in range(self.settings_retry_profile.count()):
                        if str(self.settings_retry_profile.itemData(i) or "") == retry_val:
                            self.settings_retry_profile.setCurrentIndex(i)
                            break
                    self._video_retry_profile = retry_val
                except Exception:
                    for i in range(self.settings_retry_profile.count()):
                        if str(self.settings_retry_profile.itemData(i) or "") == "stable":
                            self.settings_retry_profile.setCurrentIndex(i)
                            break
                    self._video_retry_profile = "stable"
                try:
                    self.settings_log_visible.setCurrentText(str(self.settings.value("log/visible_lines", 500) or 500))
                except Exception:
                    self.settings_log_visible.setCurrentText("500")
                try:
                    self.settings_log_store.setCurrentText(str(self.settings.value("log/max_lines", 5000) or 5000))
                except Exception:
                    self.settings_log_store.setCurrentText("5000")

                # Language selector (persisted).
                try:
                    lang = self._read_ui_language()
                    self._ui_language = lang
                    self._ui = get_ui_strings(lang)
                    b = self.settings_language_buttons.get(lang)
                    if b is not None:
                        b.setChecked(True)
                except Exception:
                    pass
        except Exception:
            pass

        # Apply strings once at the end so the UI matches persisted language.
        try:
            self.apply_ui_strings(self._ui)
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
        QShortcut(QKeySequence("Ctrl+`"), self, activated=self.toggle_system_log_collapsed)
        QShortcut(QKeySequence(Qt.Key_F1), self, activated=self.show_shortcuts_help)
        # Esc handled via keyPressEvent for deterministic priority logic.

    def show_shortcuts_help(self) -> None:
        self._show_banner(
            "muted",
            self._ui.shortcuts_help,
            auto_hide_ms=12_000,
        )

    def _read_ui_language(self) -> str:
        if self.settings is None:
            return "en"
        v = self.settings.value(self.SETTINGS_KEY_UI_LANGUAGE, None)
        if v is None or str(v).strip() == "":
            v = self.settings.value("ui_language", None)
        return normalize_ui_language(str(v or "en"))

    def _set_ui_language(self, lang: str) -> None:
        v = normalize_ui_language(lang)
        try:
            if self.settings is not None:
                self.settings.setValue(self.SETTINGS_KEY_UI_LANGUAGE, v)
                # Best-effort: keep a flat key too (tools/tests/legacy).
                self.settings.setValue("ui_language", v)
        except Exception:
            pass

        self._ui_language = v
        # Update the global `UI` proxy for all modules, then re-apply to existing widgets.
        self.apply_ui_strings(set_ui_language(v))

        # Refresh dynamic text surfaces that are state-derived (not only static labels).
        try:
            self._render_state()
        except Exception:
            pass

    def apply_ui_strings(self, strings: UiStrings) -> None:
        self._ui = strings

        # Window / title
        try:
            self.setWindowTitle(strings.app_title)
        except Exception:
            pass
        try:
            if getattr(self, "title_label", None) is not None:
                self.title_label.setText(strings.app_title)
        except Exception:
            pass

        # Header nav buttons depend on the current layout mode; re-sync after updating strings.
        try:
            self._sync_header_nav_buttons(str(getattr(self, "_layout_id", "A") or "A"))
        except Exception:
            pass

        # State badges (connection / scanning / connecting) must be re-rendered in the new language.
        try:
            self._apply_primary_state_badge(self.phase)
        except Exception:
            pass
        try:
            if getattr(self, "badge_video", None) is not None and getattr(self, "hud_video", None) is not None:
                if bool(getattr(self, "video_active", False)):
                    self.badge_video.setText(strings.badge_video_on)
                    self.hud_video.setText(strings.badge_video_on)
                else:
                    self.badge_video.setText(strings.badge_video_off)
                    self.hud_video.setText(strings.badge_video_off)
        except Exception:
            pass

        # Premium stability: keep header badge widths fixed per language/state set.
        try:
            self._apply_header_badge_fixed_widths()
        except Exception:
            pass
        try:
            self._sync_window_controls()
        except Exception:
            pass
        # Exit confirm modal widgets can be lazily created; keep them in sync with UI language.
        try:
            if self._exit_confirm_title is not None:
                self._exit_confirm_title.setText(strings.exit_confirm_title)
            if self._exit_confirm_body is not None:
                # Body copy is per-invocation (risky vs idle); keep a safe default here.
                self._exit_confirm_body.setText(strings.exit_confirm_body_idle)
            if self._exit_confirm_btn_cancel is not None:
                self._exit_confirm_btn_cancel.setText(strings.exit_confirm_cancel)
            if self._exit_confirm_btn_exit is not None:
                self._exit_confirm_btn_exit.setText(strings.exit_confirm_exit)
        except Exception:
            pass

        # Left panel
        try:
            self.search.setPlaceholderText(strings.search_placeholder)
            self.list_hint.setText(strings.list_hint)
            self.btn_scan.setText(strings.scan_button)
            self.btn_scan.setToolTip(strings.scan_tooltip)
            self.btn_connect.setText(strings.connect_button)
            self.btn_connect.setToolTip(strings.connect_tooltip)
            self.btn_disconnect.setText(strings.disconnect_button)
            self.btn_disconnect.setToolTip(strings.disconnect_tooltip)
        except Exception:
            pass

        # System log panel (embedded)
        try:
            if getattr(self, "system_log_title", None) is not None:
                self.system_log_title.setText(strings.log_dock_title)
            self.log_filter.setPlaceholderText(strings.log_filter_placeholder)
            self.btn_pause_log.setToolTip(strings.log_pause_tooltip)
            self.btn_clear_log.setToolTip(strings.log_clear_tooltip)
            # Keep current pause state label consistent.
            self.btn_pause_log.setText(strings.log_resume if self.btn_pause_log.isChecked() else strings.log_pause)
            self.btn_clear_log.setText(strings.log_clear)
            if getattr(self, "btn_collapse_log", None) is not None:
                self.btn_collapse_log.setAccessibleName(strings.log_toggle_accessible_name)
                self.btn_collapse_log.setAccessibleDescription(strings.log_toggle_accessible_desc)
                # Re-apply the glyph according to current collapsed state.
                try:
                    sizes = self.left_splitter.sizes()
                    collapsed = bool(sizes and len(sizes) > 1 and int(sizes[1]) <= 1)
                except Exception:
                    collapsed = False
                self.btn_collapse_log.setText(
                    strings.log_collapse_glyph_collapsed if collapsed else strings.log_collapse_glyph_expanded
                )
            # Refresh empty placeholder text if log is empty.
            self.refresh_log_view()
        except Exception:
            pass

        # Mid / Drive
        try:
            self.live_video_label.setText(strings.live_video_label)
            self.telemetry_caption.setText(strings.telemetry_label)
            self.drive_guard_title.setText(strings.drive_guard_title)
            self.drive_guard_body.setText(strings.drive_guard_body)
            self.drive_guard_action.setText(strings.dashboard_button)
            self.video_view.setText(strings.video_not_available)
            self.btn_video_help.setText(strings.video_requirements_button)
            self.btn_video_help.setToolTip(strings.video_requirements_tooltip)
            self.btn_overlay_disconnect.setText(strings.overlay_disconnect_button)
            self.btn_overlay_disconnect.setToolTip(strings.overlay_disconnect_tooltip)
        except Exception:
            pass

        # Settings panel
        try:
            self.settings_title.setText(strings.settings_title)
            self.settings_status_box.setTitle(strings.settings_section_status)
            self.settings_display_box.setTitle(strings.settings_section_display)
            self.settings_behavior_box.setTitle(strings.settings_section_behavior)
            self.settings_video_box.setTitle(strings.settings_section_video)
            self.settings_logs_box.setTitle(strings.settings_section_logs)
            self.settings_status_layout_label.setText(strings.settings_status_layout)
            self.settings_status_phase_label.setText(strings.settings_status_phase)
            self.settings_status_fullscreen_label.setText(strings.settings_status_fullscreen)
            self.settings_status_platform_label.setText(strings.settings_status_platform)
            self.settings_theme_label.setText(strings.settings_theme_label)
            self.settings_density_label.setText(strings.settings_density_label)
            self.settings_language_label.setText(strings.settings_language_label)
        except Exception:
            pass

        try:
            self.settings_receiver_latency_label.setText(strings.settings_receiver_latency_label)
            self.settings_retry_profile_label.setText(strings.settings_retry_profile_label)
            self.settings_visible_lines_label.setText(strings.settings_visible_lines_label)
            self.settings_stored_lines_label.setText(strings.settings_stored_lines_label)
            self.settings_theme.setToolTip(strings.settings_tooltip_theme)
            self.settings_density.setToolTip(strings.settings_tooltip_density)
            self.settings_auto_scan.setText(strings.settings_auto_scan)
            self.settings_auto_scan.setToolTip(strings.settings_tooltip_auto_scan)
            self.settings_auto_connect_single.setText(strings.settings_auto_connect_single)
            self.settings_auto_connect_single.setToolTip(strings.settings_tooltip_auto_connect_single)
            self.settings_start_fullscreen.setText(strings.settings_start_fullscreen)
            self.settings_start_fullscreen.setToolTip(strings.settings_tooltip_start_fullscreen)
            self.settings_video_latency.setToolTip(strings.settings_tooltip_receiver_latency)
            self.settings_retry_profile.setToolTip(strings.settings_tooltip_retry_profile)
            self.settings_log_visible.setToolTip(strings.settings_tooltip_visible_lines)
            self.settings_log_store.setToolTip(strings.settings_tooltip_stored_lines)
            self.settings_copy_diag.setText(strings.settings_copy_diagnostics)
            self.settings_apply.setText(strings.settings_apply)
            self.settings_copy_diag.setAccessibleName(strings.settings_copy_diag_accessible_name)
            self.settings_copy_diag.setAccessibleDescription(strings.settings_copy_diag_accessible_desc)
            self.settings_apply.setAccessibleName(strings.settings_apply_accessible_name)
            self.settings_apply.setAccessibleDescription(strings.settings_apply_accessible_desc)
        except Exception:
            pass
        try:
            self._sync_settings_capabilities()
            self._update_settings_status()
        except Exception:
            pass

        # Settings option display labels (keep stored values stable).
        try:
            if getattr(self, "settings_theme", None) is not None:
                theme_map = {"slate": strings.settings_theme_slate, "glass": strings.settings_theme_glass}
                cur = str(self.settings_theme.currentData() or "slate")
                self.settings_theme.blockSignals(True)
                try:
                    self.settings_theme.clear()
                    for v in ("slate", "glass"):
                        self.settings_theme.addItem(theme_map.get(v, v), v)
                    for i in range(self.settings_theme.count()):
                        if str(self.settings_theme.itemData(i) or "") == cur:
                            self.settings_theme.setCurrentIndex(i)
                            break
                finally:
                    self.settings_theme.blockSignals(False)
        except Exception:
            pass
        try:
            if getattr(self, "settings_density", None) is not None:
                dens_map = {"normal": strings.settings_density_normal, "compact": strings.settings_density_compact}
                cur = str(self.settings_density.currentData() or "normal")
                self.settings_density.blockSignals(True)
                try:
                    self.settings_density.clear()
                    for v in ("normal", "compact"):
                        self.settings_density.addItem(dens_map.get(v, v), v)
                    for i in range(self.settings_density.count()):
                        if str(self.settings_density.itemData(i) or "") == cur:
                            self.settings_density.setCurrentIndex(i)
                            break
                finally:
                    self.settings_density.blockSignals(False)
        except Exception:
            pass
        try:
            if getattr(self, "settings_retry_profile", None) is not None:
                retry_map = {"stable": strings.settings_retry_stable, "aggressive": strings.settings_retry_aggressive}
                cur = str(self.settings_retry_profile.currentData() or "stable")
                self.settings_retry_profile.blockSignals(True)
                try:
                    self.settings_retry_profile.clear()
                    for v in ("stable", "aggressive"):
                        self.settings_retry_profile.addItem(retry_map.get(v, v), v)
                    for i in range(self.settings_retry_profile.count()):
                        if str(self.settings_retry_profile.itemData(i) or "") == cur:
                            self.settings_retry_profile.setCurrentIndex(i)
                            break
                finally:
                    self.settings_retry_profile.blockSignals(False)
        except Exception:
            pass

    def _update_bottom_hint(self) -> None:
        self._session_panel.update_bottom_hint(is_connected=bool(self.is_connected))

    # ---------------- Settings: effective state ----------------
    def _settings_layout_name(self, layout_id: str) -> str:
        s = getattr(self, "_ui", UI)
        v = str(layout_id or "").strip().upper() or "A"
        if v == "B":
            return s.settings_layout_b
        if v == "C":
            return s.settings_layout_c
        if v == "D":
            return s.settings_layout_d
        return s.settings_layout_a

    def _settings_phase_name(self) -> str:
        s = getattr(self, "_ui", UI)
        try:
            p = self.phase
        except Exception:
            p = None
        try:
            if p == AppPhase.SCANNING:
                return s.badge_scanning
            if p == AppPhase.CONNECTING:
                return s.badge_connecting
            if p == AppPhase.DISCONNECTING:
                return s.badge_disconnecting
            if p == AppPhase.CONNECTED:
                return s.badge_connected
        except Exception:
            pass
        return s.badge_disconnected

    def _sync_settings_capabilities(self) -> None:
        """Enable/disable settings that are not effectively supported on this platform."""
        try:
            if not hasattr(self, "settings_start_fullscreen"):
                return
            s = getattr(self, "_ui", UI)
            if self._is_wayland():
                self.settings_start_fullscreen.setEnabled(False)
                self.settings_start_fullscreen.setToolTip(s.settings_tooltip_start_fullscreen_disabled_wayland)
            else:
                self.settings_start_fullscreen.setEnabled(True)
                self.settings_start_fullscreen.setToolTip(s.settings_tooltip_start_fullscreen)
        except Exception:
            pass

    def _update_settings_status(self) -> None:
        try:
            if not hasattr(self, "settings_status_layout_value"):
                return
            s = getattr(self, "_ui", UI)
            layout_id = str(getattr(self, "_layout_id", "A") or "A").strip().upper() or "A"
            self.settings_status_layout_value.setText(self._settings_layout_name(layout_id))
            self.settings_status_phase_value.setText(self._settings_phase_name())
            is_fs = False
            try:
                is_fs = bool(self.isFullScreen())
            except Exception:
                try:
                    is_fs = bool(self.windowState() & Qt.WindowFullScreen)
                except Exception:
                    is_fs = False
            self.settings_status_fullscreen_value.setText(s.settings_value_yes if is_fs else s.settings_value_no)
            self.settings_status_platform_value.setText(
                s.settings_platform_wayland if self._is_wayland() else s.settings_platform_x11
            )
        except Exception:
            pass

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
        if start_layout in ("A", "B", "C", "D"):
            return start_layout
        if self.settings is None:
            return "A"
        layout_id = str(self.settings.value("layout_id", self.cfg.default_layout))
        return layout_id if layout_id in ("A", "B", "C", "D") else "A"

    def _toggle_maximize_restore(self) -> None:
        # Wayland/WSLg: window-state transitions can be flaky early in a configure cycle.
        # Always apply via the "wait for non-zero size" guard to avoid 0x0 transitions.
        if self.isMaximized():
            self._run_when_window_has_size(self.showNormal)
        else:
            self._run_when_window_has_size(self.showMaximized)
        try:
            self._sync_window_controls()
        except Exception:
            pass

    def changeEvent(self, event) -> None:
        # Keep window controls coherent with actual window state.
        try:
            if event is not None and event.type() == QEvent.Type.WindowStateChange:
                try:
                    self._sync_window_controls()
                except Exception:
                    pass
        except Exception:
            pass
        super().changeEvent(event)

    def _sync_window_controls(self) -> None:
        """
        Premium: tooltips reflect maximize vs restore state.
        Keep strings sourced from UI (i18n guardrail).
        """
        if getattr(self, "btn_win_min", None) is not None:
            self.btn_win_min.setToolTip(UI.window_minimize_tooltip)
        if getattr(self, "btn_win_close", None) is not None:
            self.btn_win_close.setToolTip(UI.window_close_tooltip)
        if getattr(self, "btn_win_max", None) is not None:
            maximized = bool(self.isMaximized())
            self.btn_win_max.setToolTip(UI.window_restore_tooltip if maximized else UI.window_maximize_tooltip)
            self.btn_win_max.setText(UI.window_restore_glyph if maximized else UI.window_maximize_glyph)

    def _start_system_move(self) -> None:
        # Best-effort: delegate move to the window manager.
        try:
            wh = self.windowHandle()
            if wh is not None:
                wh.startSystemMove()
        except Exception:
            pass

    def apply_layout(self, layout_id: str) -> None:
        _apply_layout_mgr(self, layout_id)

    def _force_end_layout_transition_if_stuck(self) -> None:
        _force_end_layout_transition_if_stuck_mgr(self)

    def _on_layout_fade_in_done(self) -> None:
        _on_layout_fade_in_done_mgr(self)

    def _apply_layout_now(self, layout_id: str) -> None:
        _apply_layout_now_impl_mgr(self, layout_id)

    def _sync_header_nav_buttons(self, layout_id: str) -> None:
        """
        Senior UX: header button text shows the destination (what happens on click).
        - In Drive (B): Drive button shows "Dashboard"
        - In Panels (C): Panels button shows "Dashboard"
        - In Settings (D): Settings button shows "Dashboard"
        - In Dashboard (A): show "Drive" and "Panels"
        """
        if layout_id == "B":
            self.btn_drive.setText(UI.dashboard_button)
            self.btn_drive.setToolTip(UI.dashboard_tooltip)
            self.btn_debug.setText(UI.panels_button)
            self.btn_debug.setToolTip(UI.panels_tooltip)
            self.btn_settings.setText(UI.settings_button)
            self.btn_settings.setToolTip(UI.settings_tooltip)
            return
        if layout_id == "C":
            self.btn_drive.setText(UI.drive_button)
            self.btn_drive.setToolTip(UI.drive_tooltip)
            self.btn_debug.setText(UI.dashboard_button)
            self.btn_debug.setToolTip(UI.dashboard_tooltip)
            self.btn_settings.setText(UI.settings_button)
            self.btn_settings.setToolTip(UI.settings_tooltip)
            return
        if layout_id == "D":
            self.btn_drive.setText(UI.drive_button)
            self.btn_drive.setToolTip(UI.drive_tooltip)
            self.btn_debug.setText(UI.panels_button)
            self.btn_debug.setToolTip(UI.panels_tooltip)
            self.btn_settings.setText(UI.dashboard_button)
            self.btn_settings.setToolTip(UI.dashboard_tooltip)
            return
        # A (Dashboard)
        self.btn_drive.setText(UI.drive_button)
        self.btn_drive.setToolTip(UI.drive_tooltip)
        self.btn_debug.setText(UI.panels_button)
        self.btn_debug.setToolTip(UI.panels_tooltip)
        self.btn_settings.setText(UI.settings_button)
        self.btn_settings.setToolTip(UI.settings_tooltip)

    def _set_fade_overlay_alpha(self, a: float) -> None:
        a = 0.0 if a < 0.0 else (1.0 if a > 1.0 else a)
        # Single source of truth for the current overlay alpha.
        self._fade_overlay_alpha = float(a)
        # Obsidian fade. Keep it subtle (not pure black).
        # Use QGraphicsOpacityEffect to avoid setStyleSheet() per frame (repolish/repaint heavy),
        # while still working correctly for non-top-level widgets.
        alpha = float(a)
        if alpha > 0:
            # Ensure geometry is valid before showing; otherwise some platforms
            # can end up with a full-window opaque overlay until the first resizeEvent.
            try:
                self._fade_overlay.setGeometry(0, 0, self.width(), self.height())
            except Exception:
                pass
            self._fade_overlay.show()
            self._fade_overlay.raise_()
        try:
            if self._fade_overlay_effect is not None:
                self._fade_overlay_effect.setOpacity(alpha)
        except Exception:
            pass
        if alpha <= 0:
            self._fade_overlay.hide()

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
        # Decide destination by current layout (not by check-state timing).
        current = str(getattr(self, "_layout_id", "A") or "A")
        self.apply_layout("A" if current == "B" else "B")

    def toggle_debug_mode(self) -> None:
        current = str(getattr(self, "_layout_id", "A") or "A")
        self.apply_layout("A" if current == "C" else "C")

    def toggle_settings_mode(self) -> None:
        current = str(getattr(self, "_layout_id", "A") or "A")
        self.apply_layout("A" if current == "D" else "D")

    def _apply_settings_from_ui(self) -> None:
        if self.settings is None:
            return
        theme = str(self.settings_theme.currentData() or "slate")
        density = str(self.settings_density.currentData() or "normal")
        auto_scan = bool(self.settings_auto_scan.isChecked())
        auto_connect_single = bool(self.settings_auto_connect_single.isChecked())
        start_fullscreen = bool(self.settings_start_fullscreen.isChecked())
        video_latency = int(self.settings_video_latency.value())
        retry_profile = str(self.settings_retry_profile.currentData() or "stable")
        log_visible = int(self.settings_log_visible.currentText() or "500")
        log_store = int(self.settings_log_store.currentText() or "5000")

        self.settings.setValue("ui/theme", theme)
        self.settings.setValue("ui/density", density)
        self.settings.setValue("ui/auto_scan", 1 if auto_scan else 0)
        self.settings.setValue("ui/auto_connect_single", 1 if auto_connect_single else 0)
        self.settings.setValue("ui/start_fullscreen", 1 if start_fullscreen else 0)
        self.settings.setValue("video/latency_ms", video_latency)
        self.settings.setValue("video/retry_profile", retry_profile)
        self.settings.setValue("log/visible_lines", log_visible)
        self.settings.setValue("log/max_lines", log_store)

        # Apply runtime knobs immediately.
        self._video_retry_profile = retry_profile
        try:
            self.cfg.log_max_lines = int(log_store)
        except Exception:
            pass
        try:
            self.log_view.setMaximumBlockCount(int(log_visible))
        except Exception:
            pass

        # Apply QSS immediately (premium UX). Density spacing changes may still require restart
        # for perfect geometry, but QSS + typography update instantly.
        try:
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(build_qss(theme=theme, density=density))
        except Exception:
            pass
        try:
            self._show_banner("ok", UI.settings_banner_applied, auto_hide_ms=2000)
        except Exception:
            pass

        # Apply fullscreen preference immediately when safe (avoid Wayland/WSLg transitions).
        try:
            if not self._is_wayland():
                if start_fullscreen:
                    self._run_when_window_has_size(self.showFullScreen)
                else:
                    if self.isFullScreen():
                        self.showNormal()
        except Exception:
            pass

    def _copy_diagnostics(self) -> None:
        text = self._build_diagnostics_text()
        try:
            cb = QApplication.clipboard()
            cb.setText(text)
        except Exception:
            pass

    def _build_diagnostics_text(self) -> str:
        parts: list[str] = []
        try:
            parts.append(f"app=rc-simulator {metadata.version('rc-simulator')}")
        except Exception:
            parts.append("app=rc-simulator (version unknown)")
        try:
            import sys

            parts.append(f"python={sys.version.split()[0]}")
        except Exception:
            pass
        try:
            parts.append(f"qt_platform={QGuiApplication.platformName()}")
        except Exception:
            pass
        try:
            import os

            parts.append(f"QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM', '')}")
            parts.append(f"XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE', '')}")
            parts.append(f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')}")
        except Exception:
            pass
        try:
            parts.append(f"theme={self.settings_theme.currentText()}")
            parts.append(f"density={self.settings_density.currentText()}")
            parts.append(f"layout={self._layout_id}")
            parts.append(f"phase={self.phase.name}")
            parts.append(f"is_connected={int(bool(self.is_connected))}")
            parts.append(f"is_scanning={int(bool(self.is_scanning))}")
            parts.append(f"is_connecting={int(bool(self.is_connecting))}")
            parts.append(f"retry_profile={self._video_retry_profile}")
            parts.append(f"video_retry_seq={self._video_retry_seq}")
            parts.append(f"log_visible={self.settings_log_visible.currentText()}")
            parts.append(f"log_store={self.settings_log_store.currentText()}")
        except Exception:
            pass
        try:
            q = getattr(self.controller, "events", None)
            if q is not None:
                qsize = None
                maxsize = None
                try:
                    qsize = q.qsize()
                except Exception:
                    qsize = None
                try:
                    maxsize = getattr(q, "maxsize", None)
                except Exception:
                    maxsize = None
                if qsize is not None:
                    parts.append(f"events_qsize={qsize}")
                if maxsize is not None:
                    parts.append(f"events_maxsize={maxsize}")
        except Exception:
            pass
        try:
            dropped = int(getattr(self.controller, "events_dropped", 0) or 0)
            dropped_oldest = int(getattr(self.controller, "events_drop_oldest", 0) or 0)
            parts.append(f"events_dropped={dropped}")
            parts.append(f"events_drop_oldest={dropped_oldest}")
        except Exception:
            pass
        return "\n".join([p for p in parts if str(p).strip()]).strip() + "\n"

    # ---------------- Core actions ----------------
    def start_scan(self) -> None:
        # Strict phase gating: never start a scan while disconnecting (even if thread has already ended).
        try:
            if bool(self.is_connected) or bool(getattr(self, "phase", None) == AppPhase.DISCONNECTING):
                self._show_banner("warn", UI.active_session_disconnect_first)
                return
        except Exception:
            pass
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
        try:
            self.phase = AppPhase.SCANNING
        except Exception:
            pass
        self._render_state()
        started = self.controller.start_scan()
        if not started:
            self.is_scanning = False
            try:
                self.phase = AppPhase.IDLE
            except Exception:
                pass
            self._render_state()
            return
        # Premium UX: short, dedicated toast copy (no layout shift).
        self._show_banner("accent", UI.toast_scan_started, auto_hide_ms=1200)
        # High-signal log entry (non-spam): start of an operator action.
        self.append_log("INFO", UI.toast_scan_started)
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
            # Premium UX: immediate feedback that we're stopping the scan.
            self._show_banner("muted", UI.toast_scan_cancelling, auto_hide_ms=1200)
            # Keep showing SCANNING until ScanDoneEvent arrives.
            self.is_scanning = True
            try:
                self.phase = AppPhase.SCANNING
            except Exception:
                pass
            self._render_state()

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
        try:
            self.phase = AppPhase.CONNECTING
        except Exception:
            pass
        self._render_state()

        ok = self.controller.connect(car)
        if not ok:
            self.is_connecting = False
            try:
                self.phase = AppPhase.IDLE
            except Exception:
                pass
            self._render_state()
            self._show_banner("warn", UI.unable_start_session_active)
            return
        self._start_video_for_car(car)
        # In Drive mode we force fullscreen.
        if self.btn_drive.isChecked():
            self.apply_layout("B")
        self._refresh_pulse_state()

    def disconnect_session(self) -> None:
        self._video_retry_seq += 1
        drive_alive = self.controller.drive_thread is not None and self.controller.drive_thread.is_alive()
        scan_alive = self.controller.scan_thread is not None and self.controller.scan_thread.is_alive()
        if not drive_alive and not scan_alive:
            self.session_label.setText(f"{UI.session_status_prefix}{UI.session_inactive}")
            self.set_connection_state(False)
            self.badge_moza.setText(format_moza_badge(state="unknown"))
            self.active_car_id = None
            self._refresh_car_row_active_styles()
            self.is_connecting = False
            self._render_state()
            return
        self.append_log("WARN", UI.disconnect_requested)
        try:
            self.phase = AppPhase.DISCONNECTING
        except Exception:
            pass
        self._render_state()
        try:
            self.controller.disconnect()
        except Exception:
            pass
        self._refresh_pulse_state()

    def set_connection_state(self, connected: bool) -> None:
        self.is_connected = connected
        if connected:
            if self._session_started_mono is None:
                try:
                    self._session_started_mono = float(time.monotonic())
                except Exception:
                    self._session_started_mono = None
        else:
            self._session_started_mono = None
        try:
            self._update_time_badge()
        except Exception:
            pass
        try:
            self.phase = AppPhase.CONNECTED if connected else AppPhase.IDLE
        except Exception:
            pass
        self.btn_connect.setEnabled(not connected)
        # Overlay disconnect must always be accessible in Drive Mode (fullscreen or windowed).
        if self.btn_drive.isChecked():
            self.btn_overlay_disconnect.setVisible(connected)
            self.hud.setVisible(True)
            # Senior guard: ensure the drive guard + underlying video layers are coherent immediately,
            # without waiting for the next timer tick (prevents "Video not available" bleed-through).
            self._apply_drive_guard_state()
        self._render_state()

    def _update_time_badge(self) -> None:
        """
        Keep the center header time badge stable and lightweight.
        - When connected: show elapsed time since session started.
        - Otherwise: show placeholder.
        """
        if getattr(self, "badge_time", None) is None:
            return
        start = self._session_started_mono
        if start is None:
            self.badge_time.setText(UI.badge_time_placeholder)
            self._set_badge_kind(self.badge_time, "muted")
            return
        try:
            elapsed = max(0.0, float(time.monotonic()) - float(start))
        except Exception:
            elapsed = 0.0
        total_s = int(elapsed)
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        if h > 0:
            txt = f"{h:02d}:{m:02d}:{s:02d}"
        else:
            txt = f"{m:02d}:{s:02d}"
        self.badge_time.setText(txt)
        self._set_badge_kind(self.badge_time, "ok" if self.is_connected else "muted")

    def _apply_header_badge_fixed_widths(self) -> None:
        """
        Pixel-perfect premium header: avoid horizontal jitter by fixing badge widths
        to the maximum expected text width (current UI language).
        """
        if getattr(self, "badge_conn", None) is None:
            return

        def _fix(label: QLabel, candidates: list[str], *, pad_px: int = 18) -> None:
            fm = label.fontMetrics()
            w = 0
            for t in candidates:
                try:
                    w = max(w, int(fm.horizontalAdvance(str(t))))
                except Exception:
                    pass
            w = int(max(30, w + int(pad_px)))
            label.setFixedWidth(w)

        s = self._ui
        # Connection badge can cycle through all phases.
        _fix(
            self.badge_conn,
            [
                s.badge_scanning,
                s.badge_connecting,
                s.badge_disconnecting,
                s.badge_connected,
                s.badge_disconnected,
            ],
        )
        # MOZA badge uses glyphs + fixed-width tokens.
        _fix(
            self.badge_moza,
            [
                format_moza_badge(state="ok"),
                format_moza_badge(state="no"),
                format_moza_badge(state="wait"),
                format_moza_badge(state="unknown"),
            ],
        )
        # Video badge is a simple ON/OFF surface.
        _fix(self.badge_video, [s.badge_video_on, s.badge_video_off])
        # Output is monospaced but keep fixed width anyway (sign + 3 decimals).
        _fix(self.badge_output, ["+0.000", "-1.000"])
        # Time badge can expand to hh:mm:ss.
        _fix(self.badge_time, [s.badge_time_placeholder, "99:59:59"])

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

    def _render_state(self) -> None:
        """
        Single render entrypoint for dashboard state.

        Senior-pro invariant: if you need to refresh UI for a state change, call this.
        Avoid calling individual _update_* methods from event handlers to prevent drift.
        """
        try:
            phase = getattr(self, "phase", None)
            if phase is not None:
                self._apply_primary_state_badge(phase)
        except Exception:
            pass
        try:
            self._update_controls()
        except Exception:
            pass
        try:
            self._refresh_mid_state()
        except Exception:
            pass
        try:
            self._update_left_hint()
        except Exception:
            pass
        try:
            self._refresh_video_overlay()
        except Exception:
            pass
        try:
            self._update_bottom_hint()
        except Exception:
            pass
        try:
            self._apply_drive_guard_state()
        except Exception:
            pass
        try:
            self._refresh_pulse_state()
        except Exception:
            pass
        try:
            self._sync_settings_capabilities()
        except Exception:
            pass
        try:
            self._update_settings_status()
        except Exception:
            pass

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
        # Keep layout stable: never toggle visibility for rows above the video block.
        # Instead, clear text when we don't want to show status.
        show_status = bool(self.is_scanning or self.is_connecting)
        if not show_status:
            try:
                self.session_label.setText("")
            except Exception:
                pass
            try:
                self.detail_label.setText("")
            except Exception:
                pass

        # Telemetry summary is the persistent dashboard readout.
        # Only overwrite when we don't have a live telemetry payload to show.
        try:
            cur = str(self.telemetry_label.text() or "").strip()
            if self.is_scanning:
                if not cur or cur == UI.session_inactive:
                    self.telemetry_label.setText(UI.mid_state_scanning_title)
            elif self.is_connecting:
                if not cur or cur == UI.session_inactive:
                    self.telemetry_label.setText(UI.mid_state_connecting_title)
            elif not self.is_connected:
                if cur != UI.session_inactive:
                    self.telemetry_label.setText(UI.session_inactive)
        except Exception:
            pass
        # NOTE: mid-state and left-hint are rendered via _render_state() only.

    def _update_left_hint(self) -> None:
        # One compact hint under Search; avoid duplicated status elsewhere.
        if self.is_connected:
            # Preserve reserved space to avoid layout jumps.
            self.list_hint.setText("")
            return
        if self.is_scanning:
            self.list_hint.setText(UI.list_hint_scanning)
            return
        if self.cars:
            self.list_hint.setText(UI.list_hint_found.format(count=len(self.cars)))
            return
        self.list_hint.setText(UI.list_hint)

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
        msg = str(getattr(self, "_video_last_help_message", "") or "").strip()
        if not msg:
            msg = UI.video_not_available
        self._show_banner(
            "muted",
            UI.video_error_help.format(message=msg),
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
        kind = str(kind or "muted")

        # Enterprise: dedupe + priority. Avoid toast spam and avoid downgrading danger.
        prio = {"danger": 3, "warn": 2, "accent": 1, "ok": 1, "muted": 0}
        try:
            now_ms = int(time.time() * 1000)
        except Exception:
            now_ms = 0

        try:
            cur_kind = str(self.banner.property("bannerKind") or "")
        except Exception:
            cur_kind = ""

        # If a danger toast is visible, do not overwrite it with lower priority messages.
        try:
            if self.banner.isVisible() and prio.get(cur_kind, 0) >= prio.get("danger", 3) and prio.get(kind, 0) < 3:
                return
        except Exception:
            pass

        # Dedupe: if we just showed the same toast very recently, ignore.
        try:
            if (
                msg == self._toast_last_msg
                and kind == self._toast_last_kind
                and (now_ms - int(self._toast_last_ts_ms)) < 800
            ):
                return
        except Exception:
            pass
        self._banner_token += 1
        token = int(self._banner_token)

        try:
            self._toast_last_msg = msg
            self._toast_last_kind = kind
            self._toast_last_ts_ms = int(now_ms)
        except Exception:
            pass

        if self.banner.property("bannerKind") != kind:
            self.banner.setProperty("bannerKind", kind)
            self.banner.style().unpolish(self.banner)
            self.banner.style().polish(self.banner)
        if self.banner_text.text() != msg:
            self.banner_text.setText(msg)
        if not self.banner.isVisible():
            self.banner.setVisible(True)
        try:
            if self._toast_overlay is not None and not self._toast_overlay.isVisible():
                self._toast_overlay.show()
            self._position_toast_overlay()
        except Exception:
            pass
        # Premium: slide-down + fade in (avoid reflow, keep it subtle).
        try:
            if self._toast_effect is None:
                eff = QGraphicsOpacityEffect(self.banner)
                eff.setOpacity(1.0)
                self.banner.setGraphicsEffect(eff)
                self._toast_effect = eff
            if self._toast_effect is not None:
                self._toast_effect.setOpacity(0.0)
                if self._toast_anim is not None:
                    try:
                        self._toast_anim.stop()
                    except Exception:
                        pass
                anim = QVariantAnimation(self.banner)
                anim.setDuration(160)
                anim.setEasingCurve(QEasingCurve.OutCubic)

                def _on_val(v) -> None:
                    try:
                        if self._toast_effect is not None:
                            self._toast_effect.setOpacity(float(v))
                        if self._toast_anchor is not None:
                            # Slide from slightly higher y to anchor y.
                            dy = int(round((1.0 - float(v)) * 6.0))
                            if self._toast_overlay is not None:
                                self._toast_overlay.move(int(self._toast_anchor.x()), int(self._toast_anchor.y() - dy))
                    except Exception:
                        pass

                anim.valueChanged.connect(_on_val)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.start()
                self._toast_anim = anim
        except Exception:
            pass

        # Drive Mode: use the drive toast overlay instead of the header toast.
        want_drive_visible = bool(self.btn_drive.isChecked())
        try:
            if want_drive_visible:
                # Hide header toast to avoid duplicates/solapados.
                try:
                    self.banner.setVisible(False)
                    if self._toast_overlay is not None:
                        self._toast_overlay.hide()
                except Exception:
                    pass

                if self.drive_banner.property("bannerKind") != kind:
                    self.drive_banner.setProperty("bannerKind", kind)
                    self.drive_banner.style().unpolish(self.drive_banner)
                    self.drive_banner.style().polish(self.drive_banner)
                if self.drive_banner_text.text() != msg:
                    self.drive_banner_text.setText(msg)
                if not self.drive_banner.isVisible():
                    self.drive_banner.setVisible(True)
                try:
                    if (
                        getattr(self, "_drive_toast_overlay", None) is not None
                        and not self._drive_toast_overlay.isVisible()
                    ):
                        self._drive_toast_overlay.show()
                    self._position_drive_toast_overlay()
                except Exception:
                    pass

                try:
                    self._drive_toast_overlay.raise_()
                    self.drive_banner.raise_()
                    self.hud.raise_()
                    self.btn_overlay_disconnect.raise_()
                except Exception:
                    pass
            else:
                # Not in Drive: ensure drive toast is hidden.
                try:
                    self.drive_banner.setVisible(False)
                    if getattr(self, "_drive_toast_overlay", None) is not None:
                        self._drive_toast_overlay.hide()
                except Exception:
                    pass
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
        # Fade out quickly, then hide (no layout reflow because it's an overlay).
        try:
            if self._toast_anim is not None:
                try:
                    self._toast_anim.stop()
                except Exception:
                    pass
            if self._toast_effect is not None:
                anim = QVariantAnimation(self.banner)
                anim.setDuration(120)
                anim.setEasingCurve(QEasingCurve.OutCubic)

                def _on_val(v) -> None:
                    try:
                        if self._toast_effect is not None:
                            self._toast_effect.setOpacity(float(v))
                        if self._toast_anchor is not None:
                            # Slide up slightly while fading out.
                            dy = int(round((1.0 - float(v)) * 6.0))
                            if self._toast_overlay is not None:
                                self._toast_overlay.move(int(self._toast_anchor.x()), int(self._toast_anchor.y() - dy))
                    except Exception:
                        pass

                def _on_done() -> None:
                    try:
                        self.banner.setVisible(False)
                    except Exception:
                        pass
                    try:
                        if self._toast_overlay is not None:
                            self._toast_overlay.hide()
                    except Exception:
                        pass

                anim.valueChanged.connect(_on_val)
                anim.finished.connect(_on_done)
                anim.setStartValue(
                    float(getattr(self._toast_effect, "opacity", lambda: 1.0)() if self._toast_effect else 1.0)
                )
                anim.setEndValue(0.0)
                anim.start()
                self._toast_anim = anim
            else:
                self.banner.setVisible(False)
                if self._toast_overlay is not None:
                    self._toast_overlay.hide()
        except Exception:
            self.banner.setVisible(False)
            try:
                if self._toast_overlay is not None:
                    self._toast_overlay.hide()
            except Exception:
                pass
        try:
            self.drive_banner.setVisible(False)
            if getattr(self, "_drive_toast_overlay", None) is not None:
                self._drive_toast_overlay.hide()
        except Exception:
            pass
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

    def _set_system_log_collapsed(self, collapsed: bool) -> None:
        """
        Premium dashboard behavior: keep the system log as a collapsible drawer.
        This avoids constant visual noise while keeping diagnostics one click away.
        """
        try:
            sizes = self.left_splitter.sizes()
        except Exception:
            sizes = None
        if not sizes or len(sizes) < 2:
            return
        top = max(1, int(sizes[0]))
        bottom = max(0, int(sizes[1]))
        if collapsed:
            self.left_splitter.setSizes([top, 0])
            try:
                if getattr(self, "btn_collapse_log", None) is not None:
                    self.btn_collapse_log.setText(UI.log_collapse_glyph_collapsed)
            except Exception:
                pass
        else:
            # Expand to a sane default if it was fully collapsed.
            if bottom <= 1:
                bottom = max(160, int(round(top * 0.45)))
            self.left_splitter.setSizes([top, bottom])
            try:
                if getattr(self, "btn_collapse_log", None) is not None:
                    self.btn_collapse_log.setText(UI.log_collapse_glyph_expanded)
            except Exception:
                pass

    def toggle_system_log_collapsed(self) -> None:
        try:
            sizes = self.left_splitter.sizes()
        except Exception:
            return
        if not sizes or len(sizes) < 2:
            return
        collapsed = int(sizes[1]) <= 1
        want = not collapsed
        self._set_system_log_collapsed(want)
        try:
            if self.settings is not None:
                self.settings.setValue("ui/log_collapsed", 1 if want else 0)
        except Exception:
            pass

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
                # Zero-noise shutdown: ignore frames in flight during close.
                if bool(getattr(self, "_closing", False)):
                    return
                img = QImage(frame.rgb_bytes, frame.width, frame.height, QImage.Format_BGRA8888).copy()
                base = QPixmap.fromImage(img)
                self._last_video_pixmap = base

                # Cache scaled pixmap; recompute only when target size changes.
                target = self.video_view.size()
                if target.width() > 10 and target.height() > 10:
                    if (
                        getattr(self, "_last_video_scaled_size", None) != target
                        or getattr(self, "_last_video_scaled_pixmap", None) is None
                    ):
                        self._last_video_scaled_pixmap = base.scaled(target, Qt.KeepAspectRatio, Qt.FastTransformation)
                        self._last_video_scaled_size = target
                    self.video_view.setPixmap(self._last_video_scaled_pixmap)
                else:
                    self.video_view.setPixmap(base)
                self.video_view.setScaledContents(False)
                self.btn_video_help.setVisible(False)
                self.video_overlay.setVisible(False)

            QTimer.singleShot(0, _apply)

        def on_error(err: VideoError) -> None:
            def _apply_err() -> None:
                msg = str(getattr(err, "message", "") or "")
                code = getattr(err, "code", None)
                self._append_log_rate_limited("WARN", msg, key="video-error", min_interval_ms=2500)
                self.video_view.setText(UI.video_not_available)
                self.badge_video.setText(UI.badge_video_off)
                self._set_badge_kind(self.badge_video, "muted")
                self.hud_video.setText(UI.badge_video_off)
                self._set_badge_kind(self.hud_video, "muted")
                self.video_view.setPixmap(QPixmap())
                missing_deps = code == VideoErrorCode.MISSING_DEPENDENCIES
                self._video_missing_deps = bool(missing_deps)
                self.btn_video_help.setVisible(bool(missing_deps))
                if missing_deps:
                    self._video_last_help_message = msg
                    # Backend-provided message contains the actionable hint.
                    self._video_retry_enabled = False
                    self._append_log_rate_limited(
                        "INFO",
                        UI.video_error_help.format(message=msg),
                        key="video-error-help",
                        min_interval_ms=30_000,
                    )
                    return
                self._schedule_video_retry(video_port)
                self._refresh_video_overlay()

            QTimer.singleShot(0, _apply_err)

        if self._video_receiver_factory is None:
            on_error(VideoError(code=VideoErrorCode.UNKNOWN_ERROR, message=UI.video_backend_not_configured))
            return

        self._video_receiver = self._video_receiver_factory(
            port=video_port,
            latency_ms=self.cfg.video_latency_ms,
            on_frame=on_frame,
            on_error=on_error,
        )
        ok = self._video_receiver.start()
        if not ok:
            on_error(VideoError(code=VideoErrorCode.CONNECTION_FAILED, message=UI.video_backend_not_available))

    def _stop_video(self) -> None:
        self._video_retry_seq += 1
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
        self._last_video_scaled_pixmap = None
        self._last_video_scaled_size = None
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
        base = self._last_video_pixmap
        target = self.video_view.size()
        if target.width() > 10 and target.height() > 10:
            self._last_video_scaled_pixmap = base.scaled(target, Qt.KeepAspectRatio, Qt.FastTransformation)
            self._last_video_scaled_size = target
            self.video_view.setPixmap(self._last_video_scaled_pixmap)
            return
        self._last_video_scaled_pixmap = None
        self._last_video_scaled_size = None
        self.video_view.setPixmap(base)

    def _schedule_video_retry(self, video_port: int) -> None:
        if not self.is_connected:
            return
        if not self._video_retry_enabled:
            return
        delay = self._video_retry_ms
        max_ms = 5000 if str(self._video_retry_profile) == "stable" else 3000
        self._video_retry_ms = min(self._video_retry_ms * 2, int(max_ms))
        seq = int(self._video_retry_seq)

        def _retry() -> None:
            if not self.is_connected:
                return
            if seq != self._video_retry_seq:
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

            ok = False
            try:
                ok = bool(self._confirm_exit_overlay(risky=risky))
            except Exception:
                ok = False
            if not ok:
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
                    msg = QLabel(UI.stopping_system, self._shutdown_overlay)
                    msg.setProperty("badge", True)
                    msg.setProperty("badgeKind", "muted")
                    msg.setAlignment(Qt.AlignHCenter)
                    overlay_layout.addWidget(msg, 0, alignment=Qt.AlignHCenter)
                    overlay_layout.addStretch(1)
                self._shutdown_overlay.setGeometry(0, 0, self.width(), self.height())
                self._shutdown_overlay.show()
                self._shutdown_overlay.raise_()
                try:
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

    def _confirm_exit_overlay(self, *, risky: bool) -> bool:
        """
        Premium confirm modal:
        - Obsidian overlay + centered card (high contrast)
        - Avoids QMessageBox styling differences across platforms
        """
        # Lazily build (reused across invocations).
        if self._exit_confirm_overlay is None:

            class _Overlay(QWidget):
                def __init__(self, parent, on_cancel):
                    super().__init__(parent)
                    self._on_cancel = on_cancel

                def mousePressEvent(self, _event) -> None:
                    try:
                        self._on_cancel()
                    except Exception:
                        pass

                def keyPressEvent(self, e) -> None:
                    try:
                        if e.key() == Qt.Key_Escape:
                            self._on_cancel()
                            e.accept()
                            return
                        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() == Qt.NoModifier:
                            fw = self.focusWidget()
                            if isinstance(fw, QPushButton) and fw.isEnabled():
                                try:
                                    fw.click()
                                    e.accept()
                                    return
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    super().keyPressEvent(e)

            overlay = _Overlay(self, on_cancel=lambda: None)
            overlay.setObjectName("modalOverlay")
            overlay.setFocusPolicy(Qt.StrongFocus)
            try:
                eff = QGraphicsOpacityEffect(overlay)
                eff.setOpacity(0.0)
                overlay.setGraphicsEffect(eff)
                self._exit_confirm_effect = eff
            except Exception:
                self._exit_confirm_effect = None

            card = QWidget(overlay)
            card.setObjectName("modalCard")
            card.setFixedWidth(520)
            card_l = QVBoxLayout(card)
            card_l.setContentsMargins(18, 16, 18, 16)
            card_l.setSpacing(12)

            top = QWidget(card)
            top_l = QHBoxLayout(top)
            top_l.setContentsMargins(0, 0, 0, 0)
            top_l.setSpacing(12)

            icon = QLabel(top)
            try:
                pm = self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(28, 28)
                icon.setPixmap(pm)
            except Exception:
                pass
            top_l.addWidget(icon, 0, alignment=Qt.AlignTop)

            txt_col = QWidget(top)
            txt_l = QVBoxLayout(txt_col)
            txt_l.setContentsMargins(0, 0, 0, 0)
            txt_l.setSpacing(6)

            title = QLabel(UI.exit_confirm_title, txt_col)
            title.setObjectName("modalTitle")
            txt_l.addWidget(title)

            body = QLabel("", txt_col)
            body.setObjectName("modalBody")
            body.setWordWrap(True)
            txt_l.addWidget(body)

            top_l.addWidget(txt_col, 1)
            card_l.addWidget(top)

            btn_row = QWidget(card)
            btn_l = QHBoxLayout(btn_row)
            btn_l.setContentsMargins(0, 0, 0, 0)
            btn_l.setSpacing(10)
            btn_l.addStretch(1)

            btn_cancel = QPushButton(UI.exit_confirm_cancel, btn_row)
            btn_cancel.setObjectName("secondaryButton")
            btn_l.addWidget(btn_cancel)

            btn_exit = QPushButton(UI.exit_confirm_exit, btn_row)
            btn_exit.setObjectName("dangerButton")
            btn_l.addWidget(btn_exit)

            card_l.addWidget(btn_row)

            self._exit_confirm_overlay = overlay
            self._exit_confirm_card = card
            self._exit_confirm_title = title
            self._exit_confirm_body = body
            self._exit_confirm_btn_cancel = btn_cancel
            self._exit_confirm_btn_exit = btn_exit

            # Connect once; per-invocation behavior is bound via `self._exit_confirm_finish`.
            def _on_cancel_clicked() -> None:
                try:
                    f = self._exit_confirm_finish
                    if f is not None:
                        f(False)
                except Exception:
                    pass

            def _on_exit_clicked() -> None:
                try:
                    f = self._exit_confirm_finish
                    if f is not None:
                        f(True)
                except Exception:
                    pass

            try:
                btn_cancel.clicked.connect(_on_cancel_clicked)
            except Exception:
                pass
            try:
                btn_exit.clicked.connect(_on_exit_clicked)
            except Exception:
                pass

        overlay = self._exit_confirm_overlay
        card = self._exit_confirm_card
        if overlay is None or card is None:
            return False

        # Update copy for this invocation (and current language).
        body_text = UI.exit_confirm_body if risky else UI.exit_confirm_body_idle
        try:
            if self._exit_confirm_title is not None:
                self._exit_confirm_title.setText(UI.exit_confirm_title)
            if self._exit_confirm_body is not None:
                self._exit_confirm_body.setText(body_text)
            if self._exit_confirm_btn_cancel is not None:
                self._exit_confirm_btn_cancel.setText(UI.exit_confirm_cancel)
            if self._exit_confirm_btn_exit is not None:
                self._exit_confirm_btn_exit.setText(UI.exit_confirm_exit)
        except Exception:
            pass
        # Premium: add salience based on risk state (QSS-driven).
        try:
            card.setProperty("risk", bool(risky))
            card.style().unpolish(card)
            card.style().polish(card)
        except Exception:
            pass

        # Show + block using a local event loop.
        result = {"ok": False}
        loop = QEventLoop(self)

        def _finish(v: bool) -> None:
            result["ok"] = bool(v)
            try:
                loop.quit()
            except Exception:
                pass

        try:
            overlay._on_cancel = lambda: _finish(False)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Bind per-invocation finish callback (signals are connected once at creation).
        self._exit_confirm_finish = _finish

        overlay.setGeometry(0, 0, self.width(), self.height())
        card.adjustSize()
        self._recenter_exit_confirm_card()
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()
        # Default focus: safer for risky exits.
        try:
            want = self._exit_confirm_btn_cancel if risky else self._exit_confirm_btn_exit
            if want is not None:
                want.setDefault(True)
                want.setAutoDefault(True)
                want.setFocus()
            else:
                overlay.setFocus()
        except Exception:
            overlay.setFocus()

        # Fade-in (cinematic, subtle).
        try:
            eff = self._exit_confirm_effect
            if eff is not None:
                eff.setOpacity(0.0)
                if self._exit_confirm_anim is not None:
                    try:
                        self._exit_confirm_anim.stop()
                    except Exception:
                        pass
                anim = QVariantAnimation(overlay)
                anim.setDuration(140)
                anim.setEasingCurve(QEasingCurve.OutCubic)

                def _on_val(v) -> None:
                    try:
                        if self._exit_confirm_effect is not None:
                            self._exit_confirm_effect.setOpacity(float(v))
                    except Exception:
                        pass

                anim.valueChanged.connect(_on_val)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.start()
                self._exit_confirm_anim = anim
        except Exception:
            pass

        loop.exec()
        overlay.hide()
        return bool(result["ok"])

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
        # Log burst coalescing: batch into a single LogPanel update per tick.
        batched_logs: list[tuple[str, str]] = []
        for ev in drained:
            match ev:
                case StatusEvent(summary=summary, detail=detail, phase=phase):
                    # Avoid duplicated scan messaging: scanning state is already communicated via
                    # the header badge + toast + left hint. Keep reserved space but clear text.
                    if phase == AppPhase.SCANNING:
                        try:
                            self.session_label.setText("")
                        except Exception:
                            pass
                        try:
                            self.detail_label.setText("")
                        except Exception:
                            pass
                    else:
                        if summary:
                            self.session_label.setText(f"{UI.session_status_prefix}{summary}")
                        self.detail_label.setText(detail)
                    if phase is not None:
                        try:
                            self.phase = phase
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
                        did_conn_transition = False
                        if should_set_connected:
                            did_conn_transition = True
                            self.set_connection_state(True)  # calls _render_state()
                        if should_set_disconnected:
                            did_conn_transition = True
                            self.set_connection_state(False)  # calls _render_state()
                        # Single render entrypoint for all state surfaces.
                        if not did_conn_transition:
                            self._render_state()
                    else:
                        self._render_state()
                case TelemetryEvent(payload=payload):
                    if isinstance(payload, dict):
                        last_telemetry_payload = payload
                case LogEvent(level=level, message=message):
                    batched_logs.append((str(level), str(message)))
                case CarsEvent(cars=cars):
                    self.cars = list(cars) if isinstance(cars, list) else []
                    self.apply_car_filter()
                    if self.cars:
                        try:
                            self.list.setFocus()
                        except Exception:
                            pass
                    self._render_state()
                    if self.cars:
                        if (
                            len(self.cars) == 1
                            and bool(getattr(self.cfg, "auto_connect_single", True))
                            and (not self.is_connected)
                            and (not self.is_connecting)
                        ):
                            self.selected_index = 0
                            self._schedule_autoconnect(self.cars[0])
                    else:
                        pass
                case ScanDoneEvent():
                    was_scanning = bool(self.is_scanning)
                    self.is_scanning = False
                    if not self.is_connected and not self.is_connecting:
                        try:
                            self.phase = AppPhase.IDLE
                        except Exception:
                            pass
                    # If we were only scanning (not connected), ensure the session label
                    # returns to a stable idle state instead of staying on "Scanning…".
                    if not self.is_connected and not self.is_connecting:
                        self.session_label.setText(f"{UI.session_status_prefix}{UI.badge_disconnected}")
                        self.detail_label.setText("")
                    self._render_state()
                    # UX: scan completion toast (no layout shift).
                    # Guard against duplicate ScanDoneEvent emissions.
                    if was_scanning:
                        try:
                            n = int(len(self.cars or []))
                        except Exception:
                            n = 0
                        if n > 0:
                            self._show_banner("ok", UI.toast_scan_found.format(count=n), auto_hide_ms=2600)
                            self.append_log("INFO", UI.toast_scan_found.format(count=n))
                        else:
                            self._show_banner("warn", UI.toast_scan_none, auto_hide_ms=2600)
                            self.append_log("WARN", UI.toast_scan_none)
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
                    self._render_state()
                case _:
                    # Unknown event: ignore for forward-compat.
                    pass

        if batched_logs:
            try:
                self._log_panel.append_logs(batched_logs)
            except Exception:
                # Fallback: preserve logs even if batch append fails.
                for lvl, msg in batched_logs:
                    try:
                        self.append_log(str(lvl), str(msg))
                    except Exception:
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
        try:
            self._update_time_badge()
        except Exception:
            pass

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
            self._position_toast_overlay()
        except Exception:
            pass
        try:
            self._position_drive_toast_overlay()
        except Exception:
            pass
        try:
            if self._exit_confirm_overlay is not None and self._exit_confirm_overlay.isVisible():
                self._exit_confirm_overlay.setGeometry(0, 0, self.width(), self.height())
                self._recenter_exit_confirm_card()
        except Exception:
            pass
        try:
            self._apply_header_responsive_compaction()
        except Exception:
            pass
        try:
            self._resize_video_pixmap()
        except Exception:
            pass
        super().resizeEvent(event)

    def _position_drive_toast_overlay(self) -> None:
        overlay = getattr(self, "_drive_toast_overlay", None)
        if overlay is None:
            return
        if getattr(self, "drive_banner", None) is None:
            return
        if not self.drive_banner.isVisible():
            return
        parent = overlay.parentWidget() or self.video_container

        self.drive_banner.adjustSize()
        w = int(self.drive_banner.width())
        h = int(self.drive_banner.height())
        x = max(12, int((int(parent.width()) - w) / 2))
        y = max(12, int(int(parent.height()) - h - 12))
        try:
            overlay.setGeometry(int(x), int(y), int(w), int(h))
        except Exception:
            pass
        self.drive_banner.move(0, 0)
        try:
            overlay.raise_()
            self.drive_banner.raise_()
        except Exception:
            pass

    def _position_toast_overlay(self) -> None:
        overlay = self._toast_overlay
        if overlay is None:
            return
        parent = overlay.parentWidget() or self
        if getattr(self, "banner", None) is None:
            return
        if not self.banner.isVisible():
            return
        # Compute anchor under the header (global -> window coords).
        y = 12
        try:
            # QMainWindow has an internal coordinate stack; use global mapping for correctness.
            p_global = self.header_widget.mapToGlobal(QPoint(0, int(self.header_widget.height())))
            p = parent.mapFromGlobal(p_global)
            y = int(p.y()) + 8
        except Exception:
            y = 12

        max_w = max(320, int(self.width()) - 24)
        card_w = min(760, max_w)
        try:
            self.banner.setFixedWidth(int(card_w))
        except Exception:
            pass
        self.banner.adjustSize()
        try:
            w = int(parent.width())
        except Exception:
            w = int(self.width())
        x = max(12, int((w - self.banner.width()) / 2))
        self._toast_anchor = QPoint(int(x), int(y))
        # Keep overlay minimal so it never blocks the app outside the toast.
        try:
            overlay.setGeometry(int(x), int(y), int(self.banner.width()), int(self.banner.height()))
        except Exception:
            pass
        self.banner.move(0, 0)
        try:
            overlay.raise_()
            self.banner.raise_()
        except Exception:
            pass

    def _recenter_exit_confirm_card(self) -> None:
        card = self._exit_confirm_card
        overlay = self._exit_confirm_overlay
        if card is None or overlay is None:
            return
        try:
            x = max(0, int((overlay.width() - card.width()) / 2))
            y = max(0, int((overlay.height() - card.height()) / 2))
            card.move(int(x), int(y))
        except Exception:
            pass

    def _apply_header_responsive_compaction(self) -> None:
        """
        Senior UX: keep right-side actions stable under narrow widths.

        Compaction policy (in order):
        - Hide video badge first
        - Then hide time badge
        """
        w = int(self.width() or 0)
        # Tuned for the current title + buttons set. Prefer conservative thresholds.
        hide_video = w < 980
        hide_time = w < 860

        if getattr(self, "badge_video", None) is not None:
            self.badge_video.setVisible(not hide_video)
        if getattr(self, "badge_time", None) is not None:
            self.badge_time.setVisible(not hide_time)

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
            try:
                self._set_skeleton_pulse(False)
            except Exception:
                pass
            if self._pulse_timer is not None and self._pulse_timer.isActive():
                self._pulse_timer.stop()
            return

        if self._pulse_timer is not None and not self._pulse_timer.isActive():
            self._pulse_timer.start()

    def _set_skeleton_pulse(self, on: bool) -> None:
        """
        Premium: animate scan skeleton rows without reflow.
        """
        try:
            if not bool(self.is_scanning) or bool(self.cars):
                return
        except Exception:
            return
        try:
            for i in range(self.list.count()):
                item = self.list.item(i)
                if item is None:
                    continue
                row = self.list.itemWidget(item)
                if row is None or (not bool(row.property("skeleton"))):
                    continue
                for lab in row.findChildren(QLabel):
                    if bool(lab.property("skeletonBar")):
                        self._set_pulse(lab, bool(on))
        except Exception:
            return

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
        try:
            self._set_skeleton_pulse(self._pulse_on)
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
