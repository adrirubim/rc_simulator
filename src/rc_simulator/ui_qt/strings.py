from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UiStrings:
    # Generic
    app_title: str = "RC Simulator"

    # Header / badges
    badge_scanning: str = "SCANNING"
    badge_connecting: str = "CONNECTING"
    badge_disconnecting: str = "DISCONNECTING"
    badge_connected: str = "CONNECTED"
    badge_disconnected: str = "DISCONNECTED"
    badge_video_on: str = "VIDEO ON"
    badge_video_off: str = "VIDEO OFF"
    badge_moza_unknown: str = "MOZA: --"
    badge_moza_wait: str = "MOZA: …"
    badge_moza_ok: str = "MOZA: OK"
    badge_moza_no: str = "MOZA: NO"
    dashboard_button: str = "Dashboard"
    drive_button: str = "Drive"
    drive_tooltip: str = "Go to Drive."
    panels_button: str = "Panels"
    panels_tooltip: str = "Go to Panels."
    settings_button: str = "Settings"
    settings_tooltip: str = "Go to Settings."
    dashboard_tooltip: str = "Go to Dashboard."

    # Settings (Layout D)
    settings_title: str = "Settings"
    settings_section_display: str = "Display"
    settings_section_behavior: str = "Behavior"
    settings_section_video: str = "Video"
    settings_section_logs: str = "Logs"
    settings_theme_label: str = "Theme"
    settings_density_label: str = "Density"
    settings_language_label: str = "Language"
    settings_receiver_latency_label: str = "Receiver latency"
    settings_retry_profile_label: str = "Retry profile"
    settings_visible_lines_label: str = "Visible lines"
    settings_stored_lines_label: str = "Stored lines"
    settings_auto_scan: str = "Auto-scan on launch"
    settings_auto_connect_single: str = "Auto-connect when exactly 1 car is found"
    settings_copy_diagnostics: str = "Copy diagnostics"
    settings_apply: str = "Apply"
    settings_tooltip_theme: str = "UI theme."
    settings_tooltip_density: str = "UI spacing density."
    settings_tooltip_auto_scan: str = "Scan on startup."
    settings_tooltip_auto_connect_single: str = "Auto-connect if exactly one car."
    settings_tooltip_receiver_latency: str = "Video buffer latency."
    settings_tooltip_retry_profile: str = "Video retry behavior."
    settings_tooltip_visible_lines: str = "UI log lines limit."
    settings_tooltip_stored_lines: str = "Stored log lines limit."
    settings_banner_applied: str = "Settings applied."

    # Settings option labels (displayed in combos)
    settings_theme_slate: str = "Slate"
    settings_theme_glass: str = "Glass"
    settings_density_normal: str = "Normal"
    settings_density_compact: str = "Compact"
    settings_retry_stable: str = "Stable"
    settings_retry_aggressive: str = "Aggressive"

    # Session mid-state card
    mid_state_scanning_title: str = "Scanning…"
    mid_state_scanning_body: str = (
        "Searching for cars on the local network. Results will appear in the list on the left."
    )
    mid_state_connecting_title: str = "Connecting…"
    mid_state_connecting_body: str = (
        "Starting a session with the selected car. If video doesn't start, use “Video requirements”."
    )

    # Debug docks
    debug_telemetry_dock_title: str = "Telemetry"
    debug_trace_dock_title: str = "Trace"
    debug_output_label: str = "Output: {value}"
    debug_steering_label: str = "Steering (abs)"
    debug_throttle_label: str = "Throttle"
    debug_brake_label: str = "Brake"

    # Left panel
    search_placeholder: str = "Search cars…"
    list_hint: str = "Tip: run a scan to find cars on the network."
    list_hint_scanning: str = "Scanning for cars…"
    list_hint_found: str = "{count} cars found."
    scan_button: str = "Scan"
    scan_button_scanning: str = "Scanning…"
    scan_button_cancel: str = "Cancel"
    scan_tooltip: str = "Scan for cars."
    connect_button: str = "Connect"
    connect_button_connecting: str = "Connecting…"
    connect_tooltip: str = "Connect (Ctrl+Enter)."
    disconnect_button: str = "Disconnect"
    disconnect_tooltip: str = "Disconnect (Esc)."

    # Mid panel
    mid_ready: str = "Ready"
    session_status_ready: str = "Session status: Ready"
    session_status_prefix: str = "Session status: "
    session_inactive: str = "Session inactive"
    live_video_label: str = "Live video (embedded in Qt):"
    telemetry_label: str = "Telemetry:"

    # Status / errors / scan
    error_prefix: str = "Error: "
    session_ended: str = "Session ended."
    scan_complete_found: str = "Scan complete: {count} cars found."
    scan_complete_none: str = "Scan complete: no cars found."
    auto_connecting_single: str = "Auto-connecting to {name} ({ip}:{port})…  (Esc or ✕ cancels)"
    active_session_disconnect_first: str = "Active session: disconnect before starting a new scan."
    session_already_active: str = "A session is already active."
    no_cars_found_scan_first: str = "No cars found: run a scan first."
    missing_selection: str = "Missing selection: select a car from the list."
    unable_start_session_active: str = "Unable to start the session (already active)."
    disconnect_requested: str = "Disconnect requested…"
    scan_in_progress_wait_or_cancel: str = "Scan in progress: wait or cancel before connecting."
    shortcuts_help: str = (
        "Shortcuts:  Ctrl+F search  |  Ctrl+Enter connect  |  Ctrl+Shift+F log filter  |  "
        "Ctrl+L clear logs  |  Esc (Drive→Panel / Panel→Disconnect)  |  F1 help"
    )
    layout_changed: str = "Layout: {layout_id}"

    # Bottom hint
    bottom_hint_drive: str = "Ctrl+F search | Ctrl+L clear logs | Esc to exit Drive Mode"
    bottom_hint_connected: str = "Ctrl+F search | Ctrl+L clear logs | Esc to disconnect"
    bottom_hint_idle: str = "Ctrl+F search | Ctrl+L clear logs | F11 fullscreen (if supported)"

    # Drive mode safety (frameless fullscreen escape hatch)
    drive_mode_hint: str = (
        "Drive Mode: Esc exits | F11 toggles fullscreen (if supported) | Ctrl+Shift+Esc emergency exit"
    )

    # Drive guard (connect-first)
    drive_guard_title: str = "Active connection required"
    drive_guard_body: str = "Connect to a car first, then enter Drive Mode."

    # Video
    video_not_available: str = "Video: not available"
    video_connecting: str = "Video: connecting…"
    video_requirements_button: str = "Video requirements"
    video_requirements_tooltip: str = "Show video requirements."
    overlay_disconnect_button: str = "DISCONNECT"
    overlay_disconnect_tooltip: str = "Disconnect now."
    overlay_title_video: str = "Video"
    overlay_connecting: str = "Connecting…"
    overlay_waiting_connection: str = "Waiting for connection…"
    overlay_no_active_session: str = "No active session."
    overlay_video_not_available: str = "Video not available"
    overlay_missing_deps: str = "Missing GI/GStreamer dependencies for embedded video."
    overlay_no_frames: str = "No frames received. Check network/port or retry."
    overlay_retry: str = "Retry"
    video_backend_not_configured: str = "Video: backend not configured."
    video_backend_not_available: str = "Video: backend not available (GI/GStreamer)."
    video_deps_hint: str = (
        "For embedded video install: sudo apt install -y python3-gi gstreamer1.0-plugins-base gstreamer1.0-plugins-good"
    )

    # Misc overlays
    stopping_system: str = "Stopping system…"

    # Banner accessibility
    banner_dismiss_name: str = "Dismiss banner"
    banner_dismiss_desc: str = "Close and hide this notification banner"

    # Log dock
    log_dock_title: str = "System log"
    log_filter_placeholder: str = "Filter logs…"
    log_pause: str = "Pause"
    log_resume: str = "Resume"
    log_pause_tooltip: str = "Pause auto-scroll."
    log_clear: str = "Clear"
    log_clear_tooltip: str = "Clear logs."

    # Exit / shutdown
    exit_confirm_title: str = "Exit RC Simulator?"
    exit_confirm_body: str = (
        "A session is active or an operation is in progress.\n\nDo you want to disconnect/stop and exit now?"
    )
    exit_confirm_body_idle: str = "Exit the application now?"
    exit_confirm_exit: str = "Exit"
    exit_confirm_cancel: str = "Cancel"


UiLanguage = Literal["en", "it", "es"]


def normalize_ui_language(lang: str | None) -> UiLanguage:
    v = str(lang or "").strip().lower()
    if v in ("en", "it", "es"):
        return v  # type: ignore[return-value]
    return "en"


UI_STRINGS_EN = UiStrings()

UI_STRINGS_IT = UiStrings(
    badge_scanning="SCANSIONE",
    badge_connecting="CONNESSIONE",
    badge_disconnecting="DISCONNESSIONE",
    badge_connected="CONNESSO",
    badge_disconnected="DISCONNESSO",
    badge_video_on="VIDEO ON",
    badge_video_off="VIDEO OFF",
    badge_moza_unknown="MOZA: --",
    badge_moza_wait="MOZA: …",
    badge_moza_ok="MOZA: OK",
    badge_moza_no="MOZA: NO",
    dashboard_button="Dashboard",
    drive_button="Guida",
    drive_tooltip="Vai a Guida.",
    panels_button="Pannelli",
    panels_tooltip="Vai a Pannelli.",
    settings_button="Impostazioni",
    settings_tooltip="Vai a Impostazioni.",
    dashboard_tooltip="Vai a Dashboard.",
    settings_title="Impostazioni",
    settings_section_display="Schermo",
    settings_section_behavior="Comportamento",
    settings_section_video="Video",
    settings_section_logs="Log",
    settings_theme_label="Tema",
    settings_density_label="Densita'",
    settings_language_label="Lingua",
    settings_receiver_latency_label="Latenza ricevitore",
    settings_retry_profile_label="Profilo tentativi",
    settings_visible_lines_label="Righe visibili",
    settings_stored_lines_label="Righe memorizzate",
    settings_auto_scan="Scansione automatica all'avvio",
    settings_auto_connect_single="Auto-connessione quando viene trovata 1 sola auto",
    settings_copy_diagnostics="Copia diagnostica",
    settings_apply="Applica",
    settings_tooltip_theme="Tema UI.",
    settings_tooltip_density="Densita' spazi UI.",
    settings_tooltip_auto_scan="Scansiona all'avvio.",
    settings_tooltip_auto_connect_single="Auto-connessione se una sola auto.",
    settings_tooltip_receiver_latency="Latenza buffer video.",
    settings_tooltip_retry_profile="Comportamento tentativi video.",
    settings_tooltip_visible_lines="Limite righe log UI.",
    settings_tooltip_stored_lines="Limite righe log memorizzate.",
    settings_banner_applied="Impostazioni applicate.",
    settings_theme_slate="Ardesia",
    settings_theme_glass="Vetro",
    settings_density_normal="Normale",
    settings_density_compact="Compatta",
    settings_retry_stable="Stabile",
    settings_retry_aggressive="Aggressivo",
    mid_state_scanning_title="Scansione…",
    mid_state_scanning_body="Ricerca auto nella rete locale. I risultati appariranno nella lista a sinistra.",
    mid_state_connecting_title="Connessione…",
    mid_state_connecting_body=('Avvio sessione con l\'auto selezionata. Se il video non parte, usa "Requisiti video".'),
    debug_telemetry_dock_title="Telemetria",
    debug_trace_dock_title="Traccia",
    debug_output_label="Output: {value}",
    debug_steering_label="Sterzo (abs)",
    debug_throttle_label="Acceleratore",
    debug_brake_label="Freno",
    search_placeholder="Cerca auto…",
    list_hint="Suggerimento: avvia una scansione per trovare auto nella rete.",
    list_hint_scanning="Scansione auto…",
    list_hint_found="{count} auto trovate.",
    scan_button="Scansiona",
    scan_button_scanning="Scansione…",
    scan_button_cancel="Annulla",
    scan_tooltip="Scansiona auto.",
    connect_button="Connetti",
    connect_button_connecting="Connessione…",
    connect_tooltip="Connetti (Ctrl+Invio).",
    disconnect_button="Disconnetti",
    disconnect_tooltip="Disconnetti (Esc).",
    mid_ready="Pronto",
    session_status_ready="Stato sessione: Pronto",
    session_status_prefix="Stato sessione: ",
    session_inactive="Sessione inattiva",
    live_video_label="Video live (integrato in Qt):",
    telemetry_label="Telemetria:",
    error_prefix="Errore: ",
    session_ended="Sessione terminata.",
    scan_complete_found="Scansione completata: {count} auto trovate.",
    scan_complete_none="Scansione completata: nessuna auto trovata.",
    auto_connecting_single="Auto-connessione a {name} ({ip}:{port})…  (Esc o ✕ annulla)",
    active_session_disconnect_first="Sessione attiva: disconnetti prima di avviare una nuova scansione.",
    session_already_active="Una sessione e' gia' attiva.",
    no_cars_found_scan_first="Nessuna auto trovata: avvia prima una scansione.",
    missing_selection="Selezione mancante: seleziona un'auto dalla lista.",
    unable_start_session_active="Impossibile avviare la sessione (gia' attiva).",
    disconnect_requested="Disconnessione richiesta…",
    scan_in_progress_wait_or_cancel="Scansione in corso: attendi o annulla prima di connettere.",
    shortcuts_help=(
        "Scorciatoie:  Ctrl+F cerca  |  Ctrl+Invio connetti  |  Ctrl+Shift+F filtro log  |  "
        "Ctrl+L pulisci log  |  Esc (Guida->Pannelli / Pannelli->Disconnetti)  |  F1 aiuto"
    ),
    layout_changed="Layout: {layout_id}",
    bottom_hint_drive="Ctrl+F cerca | Ctrl+L pulisci log | Esc per uscire da Guida",
    bottom_hint_connected="Ctrl+F cerca | Ctrl+L pulisci log | Esc per disconnettere",
    bottom_hint_idle="Ctrl+F cerca | Ctrl+L pulisci log | F11 schermo intero (se supportato)",
    drive_mode_hint=(
        "Modalita' Guida: Esc esce | F11 schermo intero (se supportato) | Ctrl+Shift+Esc uscita emergenza"
    ),
    drive_guard_title="Connessione attiva richiesta",
    drive_guard_body="Connetti prima un'auto, poi entra in Modalita' Guida.",
    video_not_available="Video: non disponibile",
    video_connecting="Video: connessione…",
    video_requirements_button="Requisiti video",
    video_requirements_tooltip="Mostra requisiti video.",
    overlay_disconnect_button="DISCONNETTI",
    overlay_disconnect_tooltip="Disconnetti ora.",
    overlay_title_video="Video",
    overlay_connecting="Connessione…",
    overlay_waiting_connection="In attesa di connessione…",
    overlay_no_active_session="Nessuna sessione attiva.",
    overlay_video_not_available="Video non disponibile",
    overlay_missing_deps="Dipendenze GI/GStreamer mancanti per il video integrato.",
    overlay_no_frames="Nessun frame ricevuto. Controlla rete/porta o riprova.",
    overlay_retry="Riprova",
    video_backend_not_configured="Video: backend non configurato.",
    video_backend_not_available="Video: backend non disponibile (GI/GStreamer).",
    video_deps_hint=(
        "Per video integrato installa: sudo apt install -y python3-gi "
        "gstreamer1.0-plugins-base gstreamer1.0-plugins-good"
    ),
    stopping_system="Arresto sistema…",
    banner_dismiss_name="Chiudi notifica",
    banner_dismiss_desc="Chiudi e nascondi questa notifica",
    log_dock_title="Log di sistema",
    log_filter_placeholder="Filtra log…",
    log_pause="Pausa",
    log_resume="Riprendi",
    log_pause_tooltip="Metti in pausa auto-scroll.",
    log_clear="Pulisci",
    log_clear_tooltip="Pulisci log.",
    exit_confirm_title="Uscire da RC Simulator?",
    exit_confirm_body=(
        "Una sessione e' attiva o un'operazione e' in corso.\n\nVuoi disconnettere/interrompere e uscire ora?"
    ),
    exit_confirm_body_idle="Uscire dall'applicazione ora?",
    exit_confirm_exit="Esci",
    exit_confirm_cancel="Annulla",
)

UI_STRINGS_ES = UiStrings(
    badge_scanning="BUSCANDO",
    badge_connecting="CONECTANDO",
    badge_disconnecting="DESCONECTANDO",
    badge_connected="CONECTADO",
    badge_disconnected="DESCONECTADO",
    badge_video_on="VIDEO ON",
    badge_video_off="VIDEO OFF",
    badge_moza_unknown="MOZA: --",
    badge_moza_wait="MOZA: …",
    badge_moza_ok="MOZA: OK",
    badge_moza_no="MOZA: NO",
    dashboard_button="Panel",
    drive_button="Conducir",
    drive_tooltip="Ir a Conducir.",
    panels_button="Paneles",
    panels_tooltip="Ir a Paneles.",
    settings_button="Ajustes",
    settings_tooltip="Ir a Ajustes.",
    dashboard_tooltip="Ir al Panel.",
    settings_title="Ajustes",
    settings_section_display="Pantalla",
    settings_section_behavior="Comportamiento",
    settings_section_video="Video",
    settings_section_logs="Logs",
    settings_theme_label="Tema",
    settings_density_label="Densidad",
    settings_language_label="Idioma",
    settings_receiver_latency_label="Latencia del receptor",
    settings_retry_profile_label="Perfil de reintento",
    settings_visible_lines_label="Lineas visibles",
    settings_stored_lines_label="Lineas guardadas",
    settings_auto_scan="Auto-buscar al iniciar",
    settings_auto_connect_single="Auto-conectar cuando se encuentra 1 coche",
    settings_copy_diagnostics="Copiar diagnostico",
    settings_apply="Aplicar",
    settings_tooltip_theme="Tema de la UI.",
    settings_tooltip_density="Densidad de espaciado.",
    settings_tooltip_auto_scan="Buscar al iniciar.",
    settings_tooltip_auto_connect_single="Auto-conectar si hay un solo coche.",
    settings_tooltip_receiver_latency="Latencia del buffer de video.",
    settings_tooltip_retry_profile="Comportamiento de reintento del video.",
    settings_tooltip_visible_lines="Limite de lineas de log en UI.",
    settings_tooltip_stored_lines="Limite de lineas guardadas.",
    settings_banner_applied="Ajustes aplicados.",
    settings_theme_slate="Pizarra",
    settings_theme_glass="Cristal",
    settings_density_normal="Normal",
    settings_density_compact="Compacta",
    settings_retry_stable="Estable",
    settings_retry_aggressive="Agresivo",
    mid_state_scanning_title="Buscando…",
    mid_state_scanning_body="Buscando coches en la red local. Los resultados apareceran en la lista de la izquierda.",
    mid_state_connecting_title="Conectando…",
    mid_state_connecting_body=(
        'Iniciando sesion con el coche seleccionado. Si el video no inicia, usa "Requisitos de video".'
    ),
    debug_telemetry_dock_title="Telemetria",
    debug_trace_dock_title="Traza",
    debug_output_label="Salida: {value}",
    debug_steering_label="Direccion (abs)",
    debug_throttle_label="Acelerador",
    debug_brake_label="Freno",
    search_placeholder="Buscar coches…",
    list_hint="Tip: ejecuta una busqueda para encontrar coches en la red.",
    list_hint_scanning="Buscando coches…",
    list_hint_found="{count} coches encontrados.",
    scan_button="Buscar",
    scan_button_scanning="Buscando…",
    scan_button_cancel="Cancelar",
    scan_tooltip="Buscar coches.",
    connect_button="Conectar",
    connect_button_connecting="Conectando…",
    connect_tooltip="Conectar (Ctrl+Enter).",
    disconnect_button="Desconectar",
    disconnect_tooltip="Desconectar (Esc).",
    mid_ready="Listo",
    session_status_ready="Estado de sesion: Listo",
    session_status_prefix="Estado de sesion: ",
    session_inactive="Sesion inactiva",
    live_video_label="Video en vivo (embebido en Qt):",
    telemetry_label="Telemetria:",
    error_prefix="Error: ",
    session_ended="Sesion finalizada.",
    scan_complete_found="Busqueda completada: {count} coches encontrados.",
    scan_complete_none="Busqueda completada: no se encontraron coches.",
    auto_connecting_single="Auto-conectando a {name} ({ip}:{port})…  (Esc o ✕ cancela)",
    active_session_disconnect_first="Sesion activa: desconecta antes de iniciar una nueva busqueda.",
    session_already_active="Ya hay una sesion activa.",
    no_cars_found_scan_first="No se encontraron coches: ejecuta una busqueda primero.",
    missing_selection="Falta seleccion: elige un coche de la lista.",
    unable_start_session_active="No se puede iniciar la sesion (ya activa).",
    disconnect_requested="Desconexion solicitada…",
    scan_in_progress_wait_or_cancel="Busqueda en curso: espera o cancela antes de conectar.",
    shortcuts_help=(
        "Atajos:  Ctrl+F buscar  |  Ctrl+Enter conectar  |  Ctrl+Shift+F filtrar logs  |  "
        "Ctrl+L limpiar logs  |  Esc (Conducir->Paneles / Paneles->Desconectar)  |  F1 ayuda"
    ),
    layout_changed="Layout: {layout_id}",
    bottom_hint_drive="Ctrl+F buscar | Ctrl+L limpiar logs | Esc para salir de Conducir",
    bottom_hint_connected="Ctrl+F buscar | Ctrl+L limpiar logs | Esc para desconectar",
    bottom_hint_idle="Ctrl+F buscar | Ctrl+L limpiar logs | F11 pantalla completa (si es compatible)",
    drive_mode_hint=(
        "Modo Conducir: Esc sale | F11 alterna pantalla completa (si es compatible) | "
        "Ctrl+Shift+Esc salida de emergencia"
    ),
    drive_guard_title="Se requiere conexion activa",
    drive_guard_body="Conecta a un coche primero y luego entra en Modo Conducir.",
    video_not_available="Video: no disponible",
    video_connecting="Video: conectando…",
    video_requirements_button="Requisitos de video",
    video_requirements_tooltip="Mostrar requisitos de video.",
    overlay_disconnect_button="DESCONECTAR",
    overlay_disconnect_tooltip="Desconectar ahora.",
    overlay_title_video="Video",
    overlay_connecting="Conectando…",
    overlay_waiting_connection="Esperando conexion…",
    overlay_no_active_session="Sin sesion activa.",
    overlay_video_not_available="Video no disponible",
    overlay_missing_deps="Faltan dependencias GI/GStreamer para video embebido.",
    overlay_no_frames="No se recibieron frames. Revisa red/puerto o reintenta.",
    overlay_retry="Reintentar",
    video_backend_not_configured="Video: backend no configurado.",
    video_backend_not_available="Video: backend no disponible (GI/GStreamer).",
    video_deps_hint=(
        "Para video embebido instala: sudo apt install -y python3-gi "
        "gstreamer1.0-plugins-base gstreamer1.0-plugins-good"
    ),
    stopping_system="Deteniendo sistema…",
    banner_dismiss_name="Cerrar aviso",
    banner_dismiss_desc="Cerrar y ocultar esta notificacion",
    log_dock_title="Log del sistema",
    log_filter_placeholder="Filtrar logs…",
    log_pause="Pausar",
    log_resume="Reanudar",
    log_pause_tooltip="Pausar auto-scroll.",
    log_clear="Limpiar",
    log_clear_tooltip="Limpiar logs.",
    exit_confirm_title="Salir de RC Simulator?",
    exit_confirm_body=("Hay una sesion activa o una operacion en curso.\n\nQuieres desconectar/parar y salir ahora?"),
    exit_confirm_body_idle="Salir de la aplicacion ahora?",
    exit_confirm_exit="Salir",
    exit_confirm_cancel="Cancelar",
)


def get_ui_strings(lang: str | None) -> UiStrings:
    v = normalize_ui_language(lang)
    if v == "it":
        return UI_STRINGS_IT
    if v == "es":
        return UI_STRINGS_ES
    return UI_STRINGS_EN


_CURRENT_UI_STRINGS: UiStrings = UI_STRINGS_EN


class _UiStringsProxy:
    """
    Dynamic proxy so legacy `UI.*` access reflects the current language.

    Note: this does not automatically update already-set widget texts; callers still
    need to re-apply strings to existing widgets after changing language.
    """

    def __getattr__(self, name: str) -> object:
        return getattr(_CURRENT_UI_STRINGS, name)


def set_ui_language(lang: str | None) -> UiStrings:
    """
    Set the global UI language used by the `UI` proxy and return the resolved strings.
    """
    global _CURRENT_UI_STRINGS
    resolved = get_ui_strings(lang)
    _CURRENT_UI_STRINGS = resolved
    return resolved


# Backwards-compat global accessor used across the UI layer.
UI = _UiStringsProxy()
