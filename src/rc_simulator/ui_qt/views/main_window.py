from __future__ import annotations

import queue
import time
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeyEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollBar,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ...app.session_controller import SessionController
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
from ...core.settings import make_settings
from ...core.state import AppPhase
from ...ports.video import VideoFrame, VideoReceiver, VideoReceiverFactory
from ..components.banner import build_banner
from ..components.docks import build_debug_docks, build_log_dock
from ..components.header import build_header
from ..components.hud import build_hud


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
        controller: SessionController | None = None,
    ):
        super().__init__()
        self.cfg = load_config()
        self.settings = make_settings()
        self._video_receiver_factory = video_receiver_factory

        self.controller = controller or SessionController.create_default()
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

        self._car_filter_debounce_seq: int = 0

        self._last_telemetry: dict = {}
        self._telemetry_trace: list[dict] = []

        self.setWindowTitle("RC Simulator")
        self.resize(1280, 800)

        self._build_ui()
        self._install_shortcuts()
        self._restore_layout()
        self._restore_window_state()

        self.timer = QTimer(self)
        self.timer.setInterval(self.cfg.queue_poll_ms)
        self.timer.timeout.connect(self.process_ui_queue)
        self.timer.start()

        self.start_scan()

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
        root = QWidget(self)
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
        self.left_panel.setMinimumWidth(320)
        left_l = QVBoxLayout(self.left_panel)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(6 if self.cfg.density == "compact" else 8)

        self.search = QLineEdit(self.left_panel)
        self.search.setPlaceholderText("Cerca auto…")
        self.search.textChanged.connect(self._debounce_apply_car_filter)
        left_l.addWidget(self.search)

        self.list = QListWidget(self.left_panel)
        self.list.itemSelectionChanged.connect(self.on_select)
        left_l.addWidget(self.list, 1)

        self.list_hint = QLabel("Suggerimento: esegui una scansione per trovare le auto in rete.", self.left_panel)
        self.list_hint.setObjectName("muted")
        self.list_hint.setWordWrap(True)
        self.list_hint.setVisible(False)
        left_l.addWidget(self.list_hint)

        btn_row = QWidget(self.left_panel)
        btn_row_l = QHBoxLayout(btn_row)
        btn_row_l.setContentsMargins(0, 0, 0, 0)
        self.btn_scan = QPushButton("Scansione", btn_row)
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_scan.setToolTip("Scansiona la rete per trovare le auto.")
        self.btn_connect = QPushButton("Connetti", btn_row)
        self.btn_connect.setObjectName("primaryButton")
        self.btn_connect.clicked.connect(self.connect_selected)
        self.btn_connect.setToolTip("Connetti all’auto selezionata (Ctrl+Invio).")
        self.btn_disconnect = QPushButton("Disconnetti", btn_row)
        self.btn_disconnect.setObjectName("dangerButton")
        self.btn_disconnect.clicked.connect(self.disconnect_session)
        self.btn_disconnect.setToolTip("Disconnetti la sessione (Esc).")
        btn_row_l.addWidget(self.btn_scan)
        btn_row_l.addWidget(self.btn_connect)
        btn_row_l.addWidget(self.btn_disconnect)
        left_l.addWidget(btn_row)

        self.btn_scan.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_connect.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_disconnect.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))

        center_l.addWidget(self.left_panel, 0)

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

        self.mid_state_title = QLabel("Pronto", self.mid_state)
        self.mid_state_title.setObjectName("title")
        self.mid_state_body = QLabel("", self.mid_state)
        self.mid_state_body.setWordWrap(True)
        self.mid_state_body.setObjectName("muted")
        ms_l.addWidget(self.mid_state_title)
        ms_l.addWidget(self.mid_state_body)

        mid_l.addWidget(self.mid_state)

        self.session_label = QLabel("Stato sessione: Pronto", self.mid_panel)
        self.detail_label = QLabel("", self.mid_panel)
        self.phase_progress = QProgressBar(self.mid_panel)
        self.phase_progress.setRange(0, 0)
        self.phase_progress.setTextVisible(False)
        self.phase_progress.setFixedHeight(10)
        self.phase_progress.setVisible(False)

        self.telemetry_label = QLabel("Sessione inattiva", self.mid_panel)
        self.telemetry_label.setWordWrap(True)
        mid_l.addWidget(self.session_label)
        mid_l.addWidget(self.detail_label)
        mid_l.addWidget(self.phase_progress)
        mid_l.addWidget(QLabel("Video live (integrato in Qt):", self.mid_panel))

        self.video_container = QWidget(self.mid_panel)
        self.video_container.setMinimumHeight(240)
        grid = QGridLayout(self.video_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self.video_view = QLabel("Video: non disponibile", self.video_container)
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

        self.btn_video_help = QPushButton("Requisiti video", self.video_container)
        self.btn_video_help.setObjectName("secondaryButton")
        self.btn_video_help.clicked.connect(self._show_video_requirements_hint)
        self.btn_video_help.setToolTip("Mostra cosa installare per il video integrato.")
        self.btn_video_help.setVisible(False)
        grid.addWidget(self.btn_video_help, 0, 0, 1, 1, alignment=Qt.AlignBottom | Qt.AlignRight)

        self.btn_overlay_disconnect = QPushButton("DISCONNETTI", self.video_container)
        self.btn_overlay_disconnect.setObjectName("dangerButton")
        self.btn_overlay_disconnect.clicked.connect(self.disconnect_session)
        self.btn_overlay_disconnect.setVisible(False)
        self.btn_overlay_disconnect.setToolTip("Disconnetti subito (Esc).")
        grid.addWidget(self.btn_overlay_disconnect, 0, 0, 1, 1, alignment=Qt.AlignTop | Qt.AlignRight)
        self.btn_overlay_disconnect.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))

        # HUD (Drive Mode): keep essential indicators visible
        hud = build_hud(parent=self.video_container)
        self.hud = hud.widget
        self.hud_conn = hud.conn
        self.hud_moza = hud.moza
        self.hud_video = hud.video
        self.hud_output = hud.output
        grid.addWidget(self.hud, 0, 0, 1, 1, alignment=Qt.AlignTop | Qt.AlignLeft)

        # Drive banner: non-modal alerts visible even in fullscreen (layout B hides header banner)
        drive_banner = build_banner(parent=self.video_container, on_close=self._hide_banner)
        self.drive_banner = drive_banner.widget
        self.drive_banner_text = drive_banner.text
        self.drive_banner_close = drive_banner.close_button
        grid.addWidget(self.drive_banner, 0, 0, 1, 1, alignment=Qt.AlignBottom | Qt.AlignHCenter)

        mid_l.addWidget(self.video_container, 1)
        mid_l.addWidget(QLabel("Telemetria:", self.mid_panel))
        mid_l.addWidget(self.telemetry_label)

        center_l.addWidget(self.mid_panel, 1)

        root_layout.addWidget(center, 1)

        # Bottom status bar (simple label)
        self.bottom = QLabel("", root)
        self.bottom.setObjectName("muted")
        root_layout.addWidget(self.bottom)

        self.setCentralWidget(root)

        log_dock = build_log_dock(
            main_window=self,
            on_filter_changed=self.refresh_log_view,
            on_pause_toggled=self._on_pause_log_toggled,
            on_clear_clicked=self.clear_log,
        )
        self.log_dock = log_dock.dock
        self.log_filter = log_dock.filter
        self.log_view = log_dock.view
        self.btn_pause_log = log_dock.pause_button
        self.btn_clear_log = log_dock.clear_button
        self.btn_pause_log.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.btn_clear_log.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))

        debug = build_debug_docks(main_window=self)
        self.telemetry_dock = debug.telemetry_dock
        self.trace_dock = debug.trace_dock
        self.t_out = debug.t_out
        self._steer_bar = debug.steer_bar
        self._gas_bar = debug.gas_bar
        self._brake_bar = debug.brake_bar
        self.telemetry_raw = debug.telemetry_raw
        self.trace_view = debug.trace_view

        self.log_store: list[tuple[str, str, str]] = []  # (ts, level, text)
        self._log_user_scrolling = False
        self._log_auto_paused = False
        self._log_scrollbar: QScrollBar = self.log_view.verticalScrollBar()
        self._log_scrollbar.valueChanged.connect(self._on_log_scroll_changed)
        self._log_last_render_was_filtered = False

        self._update_controls()
        self._refresh_mid_state()
        self._refresh_video_overlay()

        self._last_video_pixmap: QPixmap | None = None
        self._log_widget_limit = 500
        self._update_bottom_hint()

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
            (
                "Scorciatoie:  Ctrl+F cerca  |  Ctrl+Invio connetti  |  Ctrl+Shift+F filtro log  |  "
                "Ctrl+L pulisci log  |  Esc (Guida→Pannello / Pannello→Disconnetti)  |  F1 aiuto"
            ),
            auto_hide_ms=12_000,
        )

    def _update_bottom_hint(self) -> None:
        # Keep hints consistent with Esc logic and current layout.
        if self.btn_drive.isChecked() and self.isFullScreen():
            self.bottom.setText("Ctrl+F cerca | Ctrl+L pulisci log | Esc per uscire dalla modalità Guida")
            return
        if self.is_connected:
            self.bottom.setText("Ctrl+F cerca | Ctrl+L pulisci log | Esc per disconnettere")
            return
        self.bottom.setText("Ctrl+F cerca | Ctrl+L pulisci log | Esc per schermo intero")

    # ---------------- Persistence / layouts ----------------
    def _restore_layout(self) -> None:
        layout_id = str(self.settings.value("layout_id", self.cfg.default_layout))
        # Never auto-start in fullscreen Drive Mode: if last session ended in B, restore to A.
        if layout_id == "B":
            layout_id = "A"
        self.apply_layout(layout_id if layout_id in ("A", "B", "C") else "A")

    def apply_layout(self, layout_id: str) -> None:
        self.settings.setValue("layout_id", layout_id)
        if layout_id == "B":
            self.btn_drive.setChecked(True)
            self.log_dock.hide()
            self.btn_overlay_disconnect.setVisible(self.is_connected)
            self.telemetry_dock.hide()
            self.trace_dock.hide()
            self.header_widget.hide()
            self.left_panel.hide()
            self.bottom.hide()
            self.hud.setVisible(True)
            self.showFullScreen()
            self._update_bottom_hint()
        else:
            self.showNormal()
            self.btn_overlay_disconnect.setVisible(False)
            self.hud.setVisible(False)
            self.header_widget.show()
            self.left_panel.show()
            self.bottom.show()
            if layout_id == "C":
                self.log_dock.show()
                self.telemetry_dock.show()
                self.trace_dock.show()
                self.btn_debug.setChecked(True)
            else:
                self.btn_drive.setChecked(False)
                self.btn_debug.setChecked(False)
                self.log_dock.show()
                self.telemetry_dock.hide()
                self.trace_dock.hide()
            self._update_bottom_hint()

    def toggle_drive_mode(self) -> None:
        self.apply_layout("B" if self.btn_drive.isChecked() else "A")

    def toggle_debug_mode(self) -> None:
        self.apply_layout("C" if self.btn_debug.isChecked() else "A")

    # ---------------- Core actions ----------------
    def start_scan(self) -> None:
        if self.controller.drive_thread is not None and self.controller.drive_thread.is_alive():
            self._show_banner("warn", "Sessione attiva: disconnetti prima di avviare una nuova scansione.")
            return
        if self.controller.scan_thread is not None and self.controller.scan_thread.is_alive():
            return
        self.is_scanning = True
        self.badge_scan.setVisible(True)
        self._set_badge_kind(self.badge_scan, "warn")
        self._update_controls()
        started = self.controller.start_scan()
        if not started:
            self.is_scanning = False
            self.badge_scan.setVisible(False)
            self._update_controls()

    def connect_selected(self) -> None:
        if self.controller.drive_thread is not None and self.controller.drive_thread.is_alive():
            self._show_banner("muted", "Esiste già una sessione attiva.")
            return
        if not self.cars:
            self._show_banner("warn", "Nessuna auto trovata: esegui prima una scansione.")
            return
        if self.selected_index is None:
            self._show_banner("warn", "Selezione mancante: seleziona un'auto dalla lista.")
            return
        if not (0 <= self.selected_index < len(self.filtered_indices)):
            self._show_banner("warn", "Selezione mancante: seleziona un'auto dalla lista.")
            return
        car = self.cars[self.filtered_indices[self.selected_index]]
        self.active_car_id = str(car.ip or "")
        self._refresh_car_row_active_styles()

        self.session_label.setText("Stato sessione: Connessione…")
        self.detail_label.setText(f"{car.name} ({car.ip}:{car.control_port})")
        self.badge_moza.setText("MOZA: …")
        self.is_connecting = True
        self._update_controls()

        ok = self.controller.connect(car)
        if not ok:
            self.is_connecting = False
            self._update_controls()
            self._show_banner("warn", "Impossibile avviare la sessione (già attiva).")
            return
        self._start_video_for_car(car)
        # In Drive mode we force fullscreen.
        if self.btn_drive.isChecked():
            self.apply_layout("B")

    def disconnect_session(self) -> None:
        if self.controller.stop_event is None:
            self.session_label.setText("Stato sessione: Nessuna sessione attiva")
            self.set_connection_state(False)
            self.badge_moza.setText("MOZA: --")
            self.active_car_id = None
            self._refresh_car_row_active_styles()
            self.is_connecting = False
            self._update_controls()
            return
        self.append_log("WARN", "Richiesta di disconnessione…")
        try:
            self.controller.disconnect()
        except Exception:
            pass

    def set_connection_state(self, connected: bool) -> None:
        self.is_connected = connected
        self.badge_conn.setText("CONNESSO" if connected else "DISCONNESSO")
        self._set_badge_kind(self.badge_conn, "ok" if connected else "warn")
        self.hud_conn.setText("CONNESSO" if connected else "DISCONNESSO")
        self._set_badge_kind(self.hud_conn, "ok" if connected else "warn")
        self.btn_connect.setEnabled(not connected)
        # Overlay disconnect must always be accessible in Drive Mode
        if self.isFullScreen() and self.btn_drive.isChecked():
            self.btn_overlay_disconnect.setVisible(connected)
            self.hud.setVisible(True)
        self._update_controls()
        self._update_bottom_hint()

    def _update_controls(self) -> None:
        has_selection = self.selected_index is not None and 0 <= int(self.selected_index) < len(self.filtered_indices)
        session_active = self.controller.stop_event is not None or (
            self.controller.drive_thread is not None and self.controller.drive_thread.is_alive()
        )
        self.btn_disconnect.setEnabled(bool(session_active or self.is_connected))
        self.btn_connect.setEnabled(
            bool(self.cars and has_selection and not session_active and not self.is_connecting and not self.is_scanning)
        )
        self.btn_scan.setEnabled(bool(not session_active and not self.is_scanning and not self.is_connecting))

        # Make state visible in the primary actions (real-time operator UX).
        self.btn_scan.setText("Scansione…" if self.is_scanning else "Scansione")
        self.btn_connect.setText("Connessione…" if self.is_connecting else "Connetti")
        self.btn_disconnect.setText("Disconnetti")
        self.phase_progress.setVisible(bool(self.is_scanning or self.is_connecting))
        self._refresh_mid_state()
        self._refresh_video_overlay()

    def _refresh_mid_state(self) -> None:
        # Single, predictable guidance area in the middle panel.
        if self.is_scanning:
            self.mid_state_title.setText("Scansione in corso…")
            self.mid_state_body.setText(
                "Sto cercando auto nella rete locale. Attendi i risultati nella lista a sinistra."
            )
            self.mid_state.setVisible(True)
            return

        if self.is_connecting:
            self.mid_state_title.setText("Connessione…")
            self.mid_state_body.setText(
                "Sto avviando la sessione con l’auto selezionata. Se il video non parte, usa “Requisiti video”."
            )
            self.mid_state.setVisible(True)
            return

        if self.is_connected:
            # Keep the mid-state hidden once connected (video + telemetry become primary).
            self.mid_state.setVisible(False)
            return

        # Not connected.
        if not self.cars:
            self.mid_state_title.setText("Nessuna auto")
            self.mid_state_body.setText(
                "Esegui una scansione per trovare le auto nella rete. Poi seleziona un’auto e premi Connetti."
            )
            self.mid_state.setVisible(True)
            return

        has_selection = self.selected_index is not None and 0 <= int(self.selected_index) < len(self.filtered_indices)
        if not has_selection:
            self.mid_state_title.setText("Seleziona un’auto")
            self.mid_state_body.setText("Scegli un’auto dalla lista a sinistra per vedere i dettagli e connetterti.")
            self.mid_state.setVisible(True)
            return

        self.mid_state_title.setText("Pronto a connettere")
        self.mid_state_body.setText("Premi Connetti per avviare la sessione. Scorciatoia: Ctrl+Invio.")
        self.mid_state.setVisible(True)

    def _show_video_requirements_hint(self) -> None:
        self._show_banner(
            "muted",
            (
                "Video integrato richiede GI/GStreamer. In Ubuntu/WSL: "
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
        # Overlay is visible when we don't have a pixmap/frame to show.
        if not self.is_connected:
            if self.is_connecting:
                self.video_overlay_title.setText("Video")
                self.video_overlay_body.setText("Connessione…")
                self.video_overlay_action.setVisible(False)
                self.video_overlay.setVisible(True)
                return
            if self.is_scanning:
                self.video_overlay_title.setText("Video")
                self.video_overlay_body.setText("In attesa di connessione…")
                self.video_overlay_action.setVisible(False)
                self.video_overlay.setVisible(True)
                return
            self.video_overlay_title.setText("Video")
            self.video_overlay_body.setText("Nessuna sessione attiva.")
            self.video_overlay_action.setVisible(False)
            self.video_overlay.setVisible(True)
            return

        if self.is_connecting:
            self.video_overlay_title.setText("Video")
            self.video_overlay_body.setText("Connessione…")
            self.video_overlay_action.setVisible(False)
            self.video_overlay.setVisible(True)
            return

        # Connected: show overlay only if we don't have a last pixmap.
        has_frame = self._last_video_pixmap is not None and (not self._last_video_pixmap.isNull())
        if has_frame:
            self.video_overlay.setVisible(False)
            return

        self.video_overlay_title.setText("Video non disponibile")
        if self._video_missing_deps:
            self.video_overlay_body.setText("Mancano dipendenze GI/GStreamer per il video integrato.")
            self.video_overlay_action.setText("Requisiti video")
            self.video_overlay_action.setVisible(True)
        else:
            self.video_overlay_body.setText("Nessun frame ricevuto. Controlla rete/porta o riprova.")
            self.video_overlay_action.setText("Riprova")
            self.video_overlay_action.setVisible(True)
        self.video_overlay.setVisible(True)

    def _show_banner(self, kind: str, text: str, *, auto_hide_ms: int = 5000) -> None:
        msg = str(text)

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
        want_drive_visible = bool(self.isFullScreen() and self.btn_drive.isChecked())
        if self.drive_banner.isVisible() != want_drive_visible:
            self.drive_banner.setVisible(want_drive_visible)
        if auto_hide_ms > 0:
            QTimer.singleShot(auto_hide_ms, self._hide_banner)

    def _hide_banner(self) -> None:
        self.banner.setVisible(False)
        self.drive_banner.setVisible(False)

    # ---------------- UI helpers ----------------
    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def focus_log_filter(self) -> None:
        self.log_filter.setFocus()
        self.log_filter.selectAll()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            # Priority:
            # 1) Drive Mode (B): return to Pannello (A), do NOT disconnect.
            if self.isFullScreen() and self.btn_drive.isChecked():
                self.apply_layout("A")
                event.accept()
                return
            # 2) Pannello/altro: se sessione attiva -> disconnetti
            if self.is_connected:
                self.disconnect_session()
                event.accept()
                return
            # 3) No session: toggle fullscreen (normal <-> fullscreen)
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
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

        self.badge_video.setText("VIDEO ON")
        self._set_badge_kind(self.badge_video, "accent")
        self.hud_video.setText("VIDEO ON")
        self._set_badge_kind(self.hud_video, "accent")
        self.video_view.setText("Video: connessione…")
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
                self.video_view.setText("Video: non disponibile")
                self.badge_video.setText("VIDEO OFF")
                self._set_badge_kind(self.badge_video, "muted")
                self.hud_video.setText("VIDEO OFF")
                self._set_badge_kind(self.hud_video, "muted")
                self.video_view.setPixmap(QPixmap())
                # Show requirements only when GI/GStreamer is missing.
                lowered = str(msg).lower()
                missing_deps = ("gstreamer non disponibile" in lowered) or ("gi/gstreamer" in lowered)
                self._video_missing_deps = bool(missing_deps)
                self.btn_video_help.setVisible(bool(missing_deps))
                # If GI/GStreamer is missing, retries are pointless.
                if missing_deps:
                    self._video_retry_enabled = False
                    self._append_log_rate_limited(
                        "INFO",
                        (
                            "Per il video integrato installa: sudo apt install -y python3-gi "
                            "gstreamer1.0-plugins-base gstreamer1.0-plugins-good"
                        ),
                        key="video-deps-hint",
                        min_interval_ms=30_000,
                    )
                    return
                self._schedule_video_retry(video_port)
                self._refresh_video_overlay()

            QTimer.singleShot(0, _apply_err)

        if self._video_receiver_factory is None:
            on_error("Video: backend non configurato.")
            return

        self._video_receiver = self._video_receiver_factory(
            port=video_port,
            latency_ms=self.cfg.video_latency_ms,
            on_frame=on_frame,
            on_error=on_error,
        )
        ok = self._video_receiver.start()
        if not ok:
            on_error("Video: backend non disponibile (GI/GStreamer).")

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
        self.video_view.setText("Video: non disponibile")
        self.video_view.setPixmap(QPixmap())
        self._last_video_pixmap = None
        self.btn_video_help.setVisible(False)
        self._refresh_video_overlay()
        self._set_badge_kind(self.badge_video, "muted")
        self.badge_video.setText("VIDEO OFF")
        self.hud_video.setText("VIDEO OFF")
        self._set_badge_kind(self.hud_video, "muted")

    def resizeEvent(self, event) -> None:
        # Keep aspect ratio on window/fullscreen resize even if frames pause.
        try:
            if self._last_video_pixmap is not None and not self._last_video_pixmap.isNull():
                pix = self._last_video_pixmap
                if self.video_view.width() > 10 and self.video_view.height() > 10:
                    pix = pix.scaled(self.video_view.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
                self.video_view.setPixmap(pix)
        except Exception:
            pass
        super().resizeEvent(event)

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
        import time

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
        try:
            geom = self.settings.value("qt/geometry")
            if geom is not None:
                self.restoreGeometry(geom)
            state = self.settings.value("qt/windowState")
            if state is not None:
                self.restoreState(state)
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        try:
            self.timer.stop()
        except Exception:
            pass

        try:
            self.controller.shutdown()
        except Exception:
            pass

        try:
            # Avoid persisting Drive Mode as the default layout.
            if str(self.settings.value("layout_id", "A")) == "B":
                self.settings.setValue("layout_id", "A")
            self.settings.setValue("qt/geometry", self.saveGeometry())
            self.settings.setValue("qt/windowState", self.saveState())
        except Exception:
            pass
        try:
            self._stop_video()
        except Exception:
            pass
        super().closeEvent(event)

    # ---------------- Cars list ----------------
    def apply_car_filter(self) -> None:
        q = (self.search.text() or "").strip().lower()
        self.list.clear()
        self.filtered_indices = []
        for idx, car in enumerate(self.cars):
            hay = f"{car.name} {car.ip} {car.control_port}".lower()
            if q and q not in hay:
                continue
            self.filtered_indices.append(idx)
            item = QListWidgetItem(self.list)
            # Two-line rich row
            row = QWidget(self.list)
            row.setObjectName("carRow")
            ip = str(car.ip or "")
            row.setProperty("active", "true" if (self.active_car_id and ip == self.active_car_id) else "false")
            rl = QVBoxLayout(row)
            if self.cfg.density == "compact":
                rl.setContentsMargins(8, 6, 8, 6)
            else:
                rl.setContentsMargins(10, 8, 10, 8)
            rl.setSpacing(2)
            title = QLabel(str(car.name), row)
            title.setObjectName("carTitle")
            subtitle = QLabel(f"{car.ip}:{car.control_port}", row)
            subtitle.setObjectName("muted")
            rl.addWidget(title)
            rl.addWidget(subtitle)
            item.setSizeHint(row.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, row)

        if self.filtered_indices:
            self.list.setCurrentRow(0)
            self.selected_index = 0
            self.list_hint.setVisible(False)
        else:
            self.selected_index = None
            self.list_hint.setVisible(True)
            # Keep the list clean; the mid-state card and hint already explain what to do.
            self.list.clearSelection()
        self._update_controls()
        self._refresh_mid_state()

    def _refresh_car_row_active_styles(self) -> None:
        # Update row properties in-place without rebuilding the list.
        active = str(self.active_car_id or "")
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is None:
                continue
            row = self.list.itemWidget(item)
            if row is None:
                continue
            kind = "false"
            try:
                # We don't persist the IP on the row; infer from its subtitle label text.
                # Subtitle format: "<ip>:<port>"
                for child in row.findChildren(QLabel):
                    if child.objectName() == "muted":
                        ip_port = (child.text() or "").split(":")[0].strip()
                        if active and ip_port == active:
                            kind = "true"
                        break
            except Exception:
                kind = "false"

            if row.property("active") != kind:
                row.setProperty("active", kind)
                row.style().unpolish(row)
                row.style().polish(row)

    def _debounce_apply_car_filter(self) -> None:
        self._car_filter_debounce_seq += 1
        seq = int(self._car_filter_debounce_seq)

        def _apply_if_latest() -> None:
            if seq != self._car_filter_debounce_seq:
                return
            self.apply_car_filter()

        QTimer.singleShot(150, _apply_if_latest)

    def on_select(self) -> None:
        rows = self.list.selectedIndexes()
        if not rows:
            return
        self.selected_index = rows[0].row()
        self._update_controls()

    # ---------------- Logs ----------------
    def append_log(self, level: str, text: str) -> None:
        lvl = (level or "INFO").upper()
        ts = time.strftime("%H:%M:%S")
        self.log_store.append((ts, lvl, str(text)))
        # Fast-path: if not filtered and not paused, append incrementally (avoids rebuilding the whole list).
        if (not (self.log_filter.text() or "").strip()) and (not self.btn_pause_log.isChecked()):
            self._log_last_render_was_filtered = False
            self._append_log_item(ts, lvl, str(text))
            # keep store bounded
            if len(self.log_store) > self.cfg.log_max_lines:
                self.log_store = self.log_store[-self.cfg.log_max_lines :]
                # keep view bounded similarly (best-effort)
                while self.log_view.count() > self.cfg.log_max_lines:
                    self.log_view.takeItem(0)
            self.log_view.scrollToBottom()
        else:
            self.refresh_log_view()

    def clear_log(self) -> None:
        self.log_store.clear()
        self.refresh_log_view()

    def refresh_log_view(self) -> None:
        f = (self.log_filter.text() or "").strip().lower()
        self._log_last_render_was_filtered = bool(f)
        sb = self.log_view.verticalScrollBar()
        was_paused = self.btn_pause_log.isChecked()
        prev_val = sb.value()
        at_bottom_before = prev_val >= (sb.maximum() - 2)

        self.log_view.clear()
        for ts, lvl, txt in self.log_store[-self.cfg.log_max_lines :]:
            line = f"{ts}  {lvl:<5} {txt}"
            if f and f not in line.lower():
                continue
            self._append_log_item(ts, lvl, txt)

        if was_paused:
            # preserve reading position
            sb.setValue(min(prev_val, sb.maximum()))
        else:
            # keep up with live tail unless user scrolled up
            if at_bottom_before:
                self.log_view.scrollToBottom()

    def _on_pause_log_toggled(self, paused: bool) -> None:
        self.btn_pause_log.setText("Riprendi" if paused else "Pausa")
        self.btn_pause_log.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay if paused else QStyle.SP_MediaPause))
        if not paused:
            self._log_auto_paused = False
            self.log_view.scrollToBottom()

    def _on_log_scroll_changed(self) -> None:
        # Auto-pause when the user scrolls up (great for debugging under heavy logs).
        if self.btn_pause_log.isChecked():
            return
        sb = self.log_view.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        near_bottom = sb.value() >= (sb.maximum() - 2)
        if not near_bottom:
            self._log_auto_paused = True
            self.btn_pause_log.setChecked(True)

    def _append_log_item(self, ts: str, lvl: str, txt: str) -> None:
        item = QListWidgetItem(self.log_view)
        wrap = QWidget(self.log_view)
        wl = QHBoxLayout(wrap)
        if self.cfg.density == "compact":
            wl.setContentsMargins(6, 5, 6, 5)
        else:
            wl.setContentsMargins(8, 6, 8, 6)
        wl.setSpacing(8)
        ts_lab = QLabel(ts, wrap)
        ts_lab.setObjectName("muted")
        lvl_badge = QLabel(lvl, wrap)
        lvl_badge.setProperty("badge", True)
        lvl_badge.setProperty("badgeKind", self._level_to_kind(lvl))
        msg = QLabel(txt, wrap)
        msg.setWordWrap(True)
        msg.setObjectName("logText")
        wl.addWidget(ts_lab, 0)
        wl.addWidget(lvl_badge, 0)
        wl.addWidget(msg, 1)
        item.setSizeHint(wrap.sizeHint())
        self.log_view.addItem(item)
        self.log_view.setItemWidget(item, wrap)
        self._enforce_log_widget_limit()

    def _enforce_log_widget_limit(self) -> None:
        # Hard guard: keep at most N widgets in the log view to prevent long-session lag.
        limit = int(getattr(self, "_log_widget_limit", 500))
        while self.log_view.count() > limit:
            item = self.log_view.takeItem(0)
            if item is None:
                return
            w = self.log_view.itemWidget(item)
            if w is not None:
                try:
                    lay = w.layout()
                    if lay is not None:
                        while lay.count() > 0:
                            child = lay.takeAt(0)
                            if child is None:
                                break
                            cw = child.widget()
                            if cw is not None:
                                cw.deleteLater()
                except Exception:
                    pass
                try:
                    self.log_view.removeItemWidget(item)
                except Exception:
                    pass
                w.deleteLater()
            del item

    # ---------------- Queue draining ----------------
    def process_ui_queue(self) -> None:
        try:
            while True:
                ev = self.ui_queue.get_nowait()
                match ev:
                    case StatusEvent(summary=summary, detail=detail, phase=phase):
                        if summary:
                            self.session_label.setText(f"Stato sessione: {summary}")
                        self.detail_label.setText(detail)
                        if phase is not None:
                            try:
                                self.phase = phase
                            except Exception:
                                pass
                            # Derive UI booleans from phase (single source of truth).
                            self.is_scanning = bool(phase == AppPhase.SCANNING)
                            self.is_connecting = bool(phase == AppPhase.CONNECTING)
                            if phase == AppPhase.CONNECTED and not self.is_connected:
                                self.set_connection_state(True)
                            if phase in (AppPhase.IDLE, AppPhase.ERROR) and self.is_connected:
                                self.set_connection_state(False)
                    case TelemetryEvent(payload=payload):
                        self.telemetry_label.setText(str(payload.get("text", "")))
                        out = payload.get("output")
                        if out is not None:
                            try:
                                self.badge_output.setText(f"{float(out):+0.3f}")
                            except Exception:
                                pass
                        if isinstance(payload, dict):
                            self._update_debug_telemetry(payload)
                    case LogEvent(level=level, message=message):
                        self.append_log(str(level), str(message))
                    case CarsEvent(cars=cars):
                        self.cars = list(cars) if isinstance(cars, list) else []
                        self.apply_car_filter()
                        if self.cars:
                            self.append_log("INFO", f"Scansione completata: {len(self.cars)} auto trovate.")
                        else:
                            self.append_log("WARN", "Scansione completata: nessuna auto trovata.")
                    case ScanDoneEvent():
                        self.is_scanning = False
                        self.badge_scan.setVisible(False)
                        self._update_controls()
                    case ErrorEvent(message=message):
                        self.append_log("ERROR", str(message))
                        self._show_banner("danger", f"Errore: {message}", auto_hide_ms=8000)
                    case MozaStateEvent(connected=ok):
                        self.badge_moza.setText("MOZA: OK" if ok else "MOZA: NO")
                        self._set_badge_kind(self.badge_moza, "ok" if ok else "warn")
                        self.hud_moza.setText("MOZA: OK" if ok else "MOZA: NO")
                        self._set_badge_kind(self.hud_moza, "ok" if ok else "warn")
                    case SessionStoppedEvent():
                        self.append_log("WARN", "Sessione terminata.")
                        self.set_connection_state(False)
                        self._stop_video()
                        self.badge_video.setText("VIDEO OFF")
                        self._set_badge_kind(self.badge_video, "muted")
                        self.badge_moza.setText("MOZA: --")
                        self._set_badge_kind(self.badge_moza, "muted")
                        self.active_car_id = None
                        self._refresh_car_row_active_styles()
                        self.is_connecting = False
                        self._update_controls()
                    case _:
                        # Unknown event: ignore for forward-compat.
                        pass
        except queue.Empty:
            return

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
