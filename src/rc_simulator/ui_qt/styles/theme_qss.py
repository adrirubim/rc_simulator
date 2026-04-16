from __future__ import annotations


def build_qss(*, theme: str = "slate", density: str = "normal") -> str:
    # Centralized Qt stylesheet (QSS).
    #
    # QSS doesn't support CSS variables; we generate the stylesheet from a small
    # set of tokens to keep the palette consistent and maintainable.
    if theme not in ("slate", "glass"):
        theme = "slate"
    if density not in ("normal", "compact"):
        density = "normal"

    # Obsidian base (avoid pure black).
    bg = "#0F172A"
    text = "rgba(226, 232, 240, 0.96)"
    text_strong = "rgba(226, 232, 240, 0.98)"
    muted = "rgba(148, 163, 184, 0.82)"
    border = "rgba(148, 163, 184, 0.18)"
    border_soft = "rgba(148, 163, 184, 0.14)"
    border_dim = "rgba(148, 163, 184, 0.16)"
    border_dimmer = "rgba(148, 163, 184, 0.12)"
    border_hover = "rgba(148, 163, 184, 0.26)"
    border_pressed = "rgba(148, 163, 184, 0.22)"
    text_disabled = "rgba(148, 163, 184, 0.55)"
    border_disabled = "rgba(148, 163, 184, 0.14)"
    fill_hover = "rgba(148, 163, 184, 0.07)"
    title_bg = "rgba(2, 6, 23, 0.32)"
    surface_disabled = "rgba(30, 41, 59, 0.14)"

    # "Glass" is implemented as translucency + subtle borders (portable).
    if theme == "glass":
        tooltip_bg = "rgba(11, 18, 32, 0.72)"
        menu_bg = "rgba(11, 18, 32, 0.78)"
        surface_weak = "rgba(15, 23, 42, 0.16)"
        surface = "rgba(15, 23, 42, 0.20)"
        surface_strong = "rgba(15, 23, 42, 0.26)"
        # Flat buttons (gradients reserved for primary).
        button_top = "rgba(15, 23, 42, 0.20)"
        button_bottom = "rgba(15, 23, 42, 0.20)"
        button_hover_top = "rgba(15, 23, 42, 0.26)"
        button_hover_bottom = "rgba(15, 23, 42, 0.26)"
        button_pressed_top = "rgba(2, 6, 23, 0.32)"
        button_pressed_bottom = "rgba(2, 6, 23, 0.32)"
        banner_bg = "rgba(11, 18, 32, 0.62)"
        chip_bg = "rgba(15, 23, 42, 0.10)"
        progress_bg = "rgba(2, 6, 23, 0.38)"
        splash_bg = "rgba(11, 18, 32, 0.72)"
        overlay_bg = "rgba(11, 18, 32, 0.42)"
        scrollbar_handle = "rgba(148, 163, 184, 0.18)"
        scrollbar_handle_hover = "rgba(148, 163, 184, 0.28)"
    else:
        tooltip_bg = "rgba(11, 18, 32, 0.92)"
        menu_bg = "rgba(11, 18, 32, 0.94)"
        surface_weak = "rgba(15, 23, 42, 0.16)"
        surface = "rgba(15, 23, 42, 0.20)"
        surface_strong = "rgba(15, 23, 42, 0.26)"
        # Flat buttons (gradients reserved for primary).
        button_top = "rgba(15, 23, 42, 0.20)"
        button_bottom = "rgba(15, 23, 42, 0.20)"
        button_hover_top = "rgba(15, 23, 42, 0.26)"
        button_hover_bottom = "rgba(15, 23, 42, 0.26)"
        button_pressed_top = "rgba(2, 6, 23, 0.32)"
        button_pressed_bottom = "rgba(2, 6, 23, 0.32)"
        banner_bg = "rgba(11, 18, 32, 0.78)"
        chip_bg = "rgba(15, 23, 42, 0.10)"
        progress_bg = "rgba(2, 6, 23, 0.38)"
        splash_bg = "rgba(11, 18, 32, 0.88)"
        overlay_bg = "rgba(11, 18, 32, 0.55)"
        scrollbar_handle = "rgba(148, 163, 184, 0.24)"
        scrollbar_handle_hover = "rgba(148, 163, 184, 0.34)"

    accent_10 = "rgba(96, 165, 250, 0.10)"
    accent_16 = "rgba(96, 165, 250, 0.16)"
    accent_22 = "rgba(96, 165, 250, 0.22)"
    accent_35 = "rgba(96, 165, 250, 0.35)"
    accent_60 = "rgba(96, 165, 250, 0.60)"
    accent_65 = "rgba(96, 165, 250, 0.65)"
    accent_70 = "rgba(96, 165, 250, 0.70)"
    accent_85 = "rgba(96, 165, 250, 0.85)"
    accent_solid = "rgba(96, 165, 250, 1.0)"
    accent_border = "rgba(96, 165, 250, 0.45)"

    ok_border = "rgba(52, 211, 153, 0.45)"
    warn_border = "rgba(251, 191, 36, 0.48)"
    danger_border = "rgba(248, 113, 113, 0.48)"
    ok_fill = "rgba(52, 211, 153, 0.12)"
    warn_fill = "rgba(251, 191, 36, 0.14)"
    danger_fill = "rgba(248, 113, 113, 0.14)"
    muted_fill = "rgba(148, 163, 184, 0.10)"
    accent_fill = "rgba(96, 165, 250, 0.12)"
    ok_text = "rgba(52, 211, 153, 0.98)"
    warn_text = "rgba(251, 191, 36, 0.98)"
    danger_text = "rgba(248, 113, 113, 0.98)"
    muted_text = "rgba(148, 163, 184, 0.92)"
    accent_text = "rgba(96, 165, 250, 0.98)"

    # Button variants
    checked_stop0 = "rgba(96, 165, 250, 0.22)"
    checked_stop1 = "rgba(30, 64, 175, 0.18)"

    primary_text = "rgba(239, 246, 255, 0.98)"
    primary_stop0 = "rgba(96, 165, 250, 0.92)"
    primary_stop1 = "rgba(37, 99, 235, 0.92)"
    primary_border = "rgba(96, 165, 250, 0.55)"
    primary_hover_stop0 = "rgba(125, 211, 252, 0.94)"
    primary_hover_stop1 = "rgba(59, 130, 246, 0.94)"
    primary_hover_border = "rgba(147, 197, 253, 0.62)"
    primary_pressed_stop0 = "rgba(59, 130, 246, 0.86)"
    primary_pressed_stop1 = "rgba(29, 78, 216, 0.86)"
    primary_pressed_border = "rgba(96, 165, 250, 0.50)"

    danger_text_btn = "rgba(255, 247, 237, 0.98)"
    danger_stop0 = "rgba(248, 113, 113, 0.92)"
    danger_stop1 = "rgba(234, 88, 12, 0.90)"
    danger_border_btn = "rgba(248, 113, 113, 0.55)"
    danger_hover_stop0 = "rgba(251, 113, 133, 0.94)"
    danger_hover_stop1 = "rgba(249, 115, 22, 0.94)"
    danger_hover_border = "rgba(253, 164, 175, 0.55)"
    danger_pressed_stop0 = "rgba(239, 68, 68, 0.86)"
    danger_pressed_stop1 = "rgba(194, 65, 12, 0.86)"
    danger_pressed_border = "rgba(248, 113, 113, 0.50)"

    # Progress gradients
    gas_stop0 = "rgba(34, 197, 94, 0.96)"
    gas_stop1 = "rgba(16, 185, 129, 0.96)"
    brake_stop0 = "rgba(239, 68, 68, 0.96)"
    brake_stop1 = "rgba(249, 115, 22, 0.96)"
    steer_stop0 = "rgba(96, 165, 250, 0.96)"
    steer_stop1 = "rgba(168, 85, 247, 0.92)"

    # Density + typography tokens
    if density == "compact":
        font_base = "11px"
        font_title = "19px"
        font_label = "12px"
        font_mono = "11px"
        font_h2 = font_title
        radius_md = "10px"
        radius_lg = "12px"
        pad_sm = "6px 8px"
        pad_md = "7px 10px"
        pad_btn = "8px 10px"
        pad_chip = "5px 8px"
        pad_icon = "5px 8px"
        btn_min_h = "30px"
        badge_min_h = "22px"
        list_pad = "6px"
    else:
        font_base = "12px"
        font_title = "20px"
        font_label = "13px"
        font_mono = "12px"
        font_h2 = font_title
        radius_md = "12px"
        radius_lg = "14px"
        pad_sm = "6px 10px"
        pad_md = "8px 10px"
        pad_btn = "9px 12px"
        pad_chip = "6px 10px"
        pad_icon = "6px 10px"
        btn_min_h = "34px"
        badge_min_h = "24px"
        list_pad = "8px"

    qss = """
/* ============================================================
   2026 Modern UI (Slate/Navy)
   Palette:
     - Background: @BG@
     - Surface: @SURFACE_STRONG@
     - Accent: @ACCENT_SOLID@
   Notes:
     - Prefer subtle rgba highlights on hover/pressed
     - Object names / dynamic properties are used for variants
   ============================================================ */

/* ---------- Base / Typography ---------- */
QWidget {
  background: @BG@;
  color: @TEXT@;
  font-family: "Segoe UI Variable", "Segoe UI";
  font-size: @FONT_BASE@;
}

QLabel[label="true"] {
  color: rgba(226, 232, 240, 0.60);
}

QLabel[mono="true"] {
  font-family: "Cascadia Mono", "Consolas";
}

QMainWindow::separator {
  background: @BORDER_SOFT@;
  width: 1px;
  height: 1px;
}

/* ---------- Tooltips / Menus ---------- */
QToolTip {
  background: @TOOLTIP_BG@;
  color: @TEXT_STRONG@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_LG@;
  padding: @PAD_SM@;
}
QMenu {
  background: @MENU_BG@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_LG@;
  padding: 6px;
}
QMenu::item {
  padding: 8px 10px;
  border-radius: @RADIUS_MD@;
}
QMenu::item:selected {
  background: @ACCENT_16@;
}

/* ---------- Focus ---------- */
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QPushButton:focus {
  outline: none;
}

/* ---------- Inputs ---------- */
QLineEdit {
  background: @SURFACE@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_MD@;
  padding: @PAD_MD@;
  selection-background-color: @ACCENT_35@;
}
QLineEdit:focus {
  border: 1px solid @ACCENT_65@;
  background: @SURFACE_STRONG@;
}
QLineEdit:hover {
  border: 1px solid @BORDER_HOVER@;
}

QComboBox, QSpinBox {
  background: @SURFACE@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_MD@;
  padding: @PAD_MD@;
  min-height: @BTN_MIN_H@;
}
QComboBox:hover, QSpinBox:hover {
  border: 1px solid @BORDER_HOVER@;
  background: @SURFACE_STRONG@;
}
QComboBox:focus, QSpinBox:focus {
  border: 1px solid @ACCENT_65@;
}
QComboBox::drop-down {
  border: none;
  width: 28px;
}
QComboBox::down-arrow {
  image: none;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid @MUTED@;
  margin-right: 10px;
}
QComboBox::down-arrow:hover {
  border-top: 6px solid @TEXT@;
}
QComboBox QAbstractItemView {
  background: @MENU_BG@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_LG@;
  padding: 6px;
  outline: none;
  selection-background-color: @ACCENT_16@;
}
QComboBox QAbstractItemView::item {
  padding: 8px 10px;
  border-radius: @RADIUS_MD@;
}
QComboBox QAbstractItemView::item:selected {
  background: @ACCENT_22@;
}

QSpinBox::up-button, QSpinBox::down-button {
  subcontrol-origin: border;
  width: 24px;
  border: none;
  background: transparent;
}
QSpinBox::up-arrow, QSpinBox::down-arrow {
  image: none;
  width: 0px;
  height: 0px;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
}
QSpinBox::up-arrow {
  border-bottom: 6px solid @MUTED@;
}
QSpinBox::down-arrow {
  border-top: 6px solid @MUTED@;
}
QSpinBox::up-arrow:hover {
  border-bottom: 6px solid @TEXT@;
}
QSpinBox::down-arrow:hover {
  border-top: 6px solid @TEXT@;
}

QCheckBox {
  spacing: 10px;
  color: @TEXT@;
}
QCheckBox::indicator {
  width: 18px;
  height: 18px;
  border-radius: 6px;
  border: 1px solid @BORDER@;
  background: @SURFACE@;
}
QCheckBox::indicator:hover {
  border: 1px solid @BORDER_HOVER@;
  background: @SURFACE_STRONG@;
}
QCheckBox::indicator:checked {
  border: 1px solid @ACCENT_BORDER@;
  background: @ACCENT_22@;
}
QCheckBox::indicator:checked:hover {
  background: @ACCENT_35@;
}

QTextEdit {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_MD@;
  padding: @PAD_MD@;
}
QTextEdit:hover {
  border: 1px solid @BORDER_HOVER@;
}
QTextEdit:focus {
  border: 1px solid @ACCENT_60@;
  background: @SURFACE@;
}

QPlainTextEdit {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_MD@;
  padding: @PAD_MD@;
}
QPlainTextEdit:hover {
  border: 1px solid @BORDER_HOVER@;
}
QPlainTextEdit:focus {
  border: 1px solid @ACCENT_60@;
  background: @SURFACE@;
}

/* Log view: readable + mono */
QPlainTextEdit#logView {
  font-family: "Cascadia Mono", "Consolas";
  font-size: @FONT_MONO@;
}

/* ---------- Settings (Layout D) ---------- */
QWidget#settingsPanel {
  background: transparent;
}
QScrollArea {
  background: transparent;
  border: none;
}
QScrollArea > QWidget > QWidget {
  background: transparent;
}
QGroupBox {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_DIM@;
  border-radius: @RADIUS_LG@;
  margin-top: 10px;
  padding: 12px;
  font-weight: 800;
}
QGroupBox::title {
  subcontrol-origin: margin;
  subcontrol-position: top left;
  padding: 0 8px;
  left: 12px;
  color: @TEXT_STRONG@;
}

/* ---------- Buttons (High-tech) ---------- */
QPushButton {
  background: @BUTTON_TOP@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_MD@;
  padding: @PAD_BTN@;
  font-weight: 600;
  min-height: @BTN_MIN_H@;
}
QPushButton:hover {
  background: @BUTTON_HOVER_TOP@;
  border: 1px solid @BORDER_HOVER@;
}
QPushButton:pressed {
  background: @BUTTON_PRESSED_TOP@;
  border: 1px solid @BORDER_PRESSED@;
}
QPushButton:checked {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 @CHECKED_STOP0@,
    stop:1 @CHECKED_STOP1@
  );
  border: 1px solid @ACCENT_BORDER@;
}
QPushButton:disabled {
  background: @SURFACE_DISABLED@;
  color: @TEXT_DISABLED@;
  border: 1px solid @BORDER_DISABLED@;
}
QPushButton#secondaryButton {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_DIM@;
  font-weight: 650;
}
QPushButton#secondaryButton:hover {
  border: 1px solid @BORDER_HOVER@;
  background: @SURFACE@;
}
QPushButton#secondaryButton:pressed {
  border: 1px solid @BORDER_PRESSED@;
  background: @SURFACE_DISABLED@;
}
QPushButton#primaryButton {
  color: @PRIMARY_TEXT@;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 @PRIMARY_STOP0@,
    stop:1 @PRIMARY_STOP1@
  );
  border: 1px solid @PRIMARY_BORDER@;
}
QPushButton#primaryButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 @PRIMARY_HOVER_STOP0@,
    stop:1 @PRIMARY_HOVER_STOP1@
  );
  border: 1px solid @PRIMARY_HOVER_BORDER@;
}
QPushButton#primaryButton:pressed {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 @PRIMARY_PRESSED_STOP0@,
    stop:1 @PRIMARY_PRESSED_STOP1@
  );
  border: 1px solid @PRIMARY_PRESSED_BORDER@;
}
QPushButton#dangerButton {
  color: @DANGER_TEXT_BTN@;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 @DANGER_STOP0@,
    stop:1 @DANGER_STOP1@
  );
  border: 1px solid @DANGER_BORDER_BTN@;
}
QPushButton#dangerButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 @DANGER_HOVER_STOP0@,
    stop:1 @DANGER_HOVER_STOP1@
  );
  border: 1px solid @DANGER_HOVER_BORDER@;
}
QPushButton#dangerButton:pressed {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 @DANGER_PRESSED_STOP0@,
    stop:1 @DANGER_PRESSED_STOP1@
  );
  border: 1px solid @DANGER_PRESSED_BORDER@;
}

/* Icon buttons (banner close, etc.) */
QPushButton#bannerClose {
  background: transparent;
  border: 1px solid @BORDER_DIM@;
  border-radius: @RADIUS_MD@;
  padding: @PAD_ICON@;
  min-width: 26px;
  min-height: 26px;
}
QPushButton#bannerClose:hover {
  background: @FILL_HOVER@;
  border: 1px solid @BORDER_HOVER@;
}
QPushButton#bannerClose:pressed {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_PRESSED@;
}

QToolButton#logCollapse {
  background: transparent;
  border: 1px solid @BORDER_DIM@;
  border-radius: @RADIUS_MD@;
  padding: 4px 8px;
  min-width: 26px;
  min-height: 26px;
  font-weight: 900;
  color: @MUTED@;
}
QToolButton#logCollapse:hover {
  background: @FILL_HOVER@;
  border: 1px solid @BORDER_HOVER@;
  color: @TEXT@;
}
QToolButton#logCollapse:pressed {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_PRESSED@;
}

/* ---------- Language selector (3 circular dots) ---------- */
QToolButton#langDot {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_DIM@;
  border-radius: 999px;
  padding: 6px 10px;
  min-width: 40px;
  min-height: 32px;
  font-weight: 800;
  letter-spacing: 0.5px;
}
QToolButton#langDot:hover {
  background: @SURFACE@;
  border: 1px solid @BORDER_HOVER@;
}
QToolButton#langDot:checked {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 @CHECKED_STOP0@,
    stop:1 @CHECKED_STOP1@
  );
  border: 1px solid @ACCENT_BORDER@;
}
QToolButton#langDot:focus {
  border: 1px solid @ACCENT_65@;
}

/* ---------- Lists ---------- */
QListWidget {
  background: @SURFACE_WEAK@;
  border: none;
  border-radius: @RADIUS_LG@;
  padding: @LIST_PAD@;
}
QListWidget::item {
  padding: 0px;
  border-radius: @RADIUS_LG@;
}
QListWidget::item:selected {
  background: @ACCENT_10@;
  border: none;
}
QListWidget::item:hover {
  background: @FILL_HOVER@;
}

/* Car list row: requires row.setObjectName("carRow") */
QWidget#carRow {
  border-radius: @RADIUS_LG@;
  background: @SURFACE_STRONG@;
  border: 1px solid @BORDER_DIMMER@;
}
QWidget#carRow[skeleton="true"] {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_DIM@;
}
QWidget#carRow:hover {
  background: @SURFACE_STRONG@;
  border: 1px solid @ACCENT_22@;
}
QWidget#carRow[active="true"] {
  border: 2px solid @ACCENT_70@;
  border-bottom: 2px solid @ACCENT_SOLID@;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 @ACCENT_16@,
    stop:1 @SURFACE_STRONG@
  );
}


/* Connected pill in car list (minimal, readable) */
QLabel#carConnectedPill {
  background: @CHIP_BG@;
  border: 1px solid {ok_border};
  color: @OK_TEXT@;
  border-radius: 999px;
  padding: @PAD_CHIP@;
  font-weight: 800;
}

/* ---------- Dock ---------- */
QDockWidget {
  titlebar-close-icon: none;
  titlebar-normal-icon: none;
}
QDockWidget::title {
  background: @TITLE_BG@;
  padding: 10px 12px;
  border: none;
  border-bottom: 1px solid @BORDER_SOFT@;
  font-weight: 800;
}
QDockWidget::widget {
  border: none;
  background: @SURFACE@;
}

/* Splitters: subtle handle, modern */
QSplitter::handle {
  background: transparent;
}
QSplitter::handle:hover {
  background: @BORDER_DIMMER@;
}
QSplitter::handle:pressed {
  background: @ACCENT_22@;
}
QSplitter::handle:vertical {
  height: 8px;
  margin: 6px 0px;
  border-radius: 6px;
}
QSplitter::handle:horizontal {
  width: 8px;
  margin: 0px 6px;
  border-radius: 6px;
}

/* System log panel container */
QWidget#systemLogPanel {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_DIM@;
  border-radius: @RADIUS_LG@;
}

/* ---------- Labels ---------- */
QLabel#title {
  font-size: @FONT_TITLE@;
  font-weight: 900;
}

/* ---------- Enterprise title bar (frameless chrome) ---------- */
QWidget#titleBar {
  background: rgba(2, 6, 23, 0.20);
  border: none;
  border-bottom: 1px solid @BORDER_SOFT@;
}
QPushButton#windowMin, QPushButton#windowMax, QPushButton#windowClose {
  background: transparent;
  border: 1px solid @BORDER_DIM@;
  border-radius: @RADIUS_LG@;
  padding: 6px 10px;
  min-width: 34px;
  min-height: 30px;
  font-weight: 700;
}
QPushButton#windowMin:hover, QPushButton#windowMax:hover {
  background: @FILL_HOVER@;
  border: 1px solid @BORDER_HOVER@;
}
QPushButton#windowClose:hover {
  background: rgba(248, 113, 113, 0.14);
  border: 1px solid rgba(248, 113, 113, 0.35);
}
QLabel#muted {
  color: @MUTED@;
}
QLabel#carTitle {
  font-size: @FONT_LABEL@;
  font-weight: 800;
}

/* Skeleton bars (premium placeholders) */
QLabel[skeletonBar="true"] {
  background: rgba(148, 163, 184, 0.14);
  border-radius: 7px;
  min-height: 14px;
}
QLabel[skeletonBar="true"][pulse="true"] {
  background: rgba(148, 163, 184, 0.22);
}
QLabel[skeletonBar="true"][skeletonSmall="true"] {
  background: rgba(148, 163, 184, 0.10);
  min-height: 10px;
  max-width: 60%;
}
QLabel[skeletonBar="true"][skeletonSmall="true"][pulse="true"] {
  background: rgba(148, 163, 184, 0.16);
}
QLabel#logText {
  color: @TEXT@;
  font-family: "Cascadia Mono", "Consolas";
  font-size: @FONT_MONO@;
}

/* ---------- Banner ---------- */
#banner {
  border-radius: @RADIUS_LG@;
  border: 1px solid @BORDER_DIM@;
  background: @BANNER_BG@;
}
#banner[bannerKind="ok"] {
  border: 1px solid {ok_border};
  background: @OK_FILL@;
}
#banner[bannerKind="warn"] {
  border: 1px solid {warn_border};
  background: @WARN_FILL@;
}
#banner[bannerKind="danger"] {
  border: 1px solid {danger_border};
  background: @DANGER_FILL@;
}
#banner[bannerKind="muted"] {
  border: 1px solid @BORDER@;
  background: @MUTED_FILL@;
}
#banner[bannerKind="accent"] {
  border: 1px solid @ACCENT_BORDER@;
  background: @ACCENT_FILL@;
}

/* ---------- Badges (chips) ---------- */
QLabel[badge="true"] {
  /* HUD backplate: keep readable over bright video feeds */
  background: rgba(15, 23, 42, 0.55);
  padding: 2px 6px;
  border-radius: 4px;
  min-height: @BADGE_MIN_H@;
  border: none;
  border-left: 8px solid @BORDER_DIMMER@;
  font-weight: 600;
}
/* ---------- Focus ring (visible) ---------- */
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QListWidget:focus {
  border: 1px solid @ACCENT_65@;
}
QPushButton:focus {
  border: 1px solid @ACCENT_65@;
}

/* ---------- Compact helpers ---------- */
QWidget#carRow {
  /* inner paddings are defined in code; this keeps visuals aligned across densities */
}

QLabel[badgeKind="ok"] { color: @OK_TEXT@; }
QLabel[badgeKind="warn"] { color: @WARN_TEXT@; }
QLabel[badgeKind="danger"] { color: @DANGER_TEXT@; }
QLabel[badgeKind="muted"] { color: @MUTED_TEXT@; }
QLabel[badgeKind="accent"] { color: @ACCENT_TEXT@; }
QLabel[badge="true"][badgeKind="ok"] {
  border-left: 8px solid {ok_border};
}
QLabel[badge="true"][badgeKind="warn"] {
  border-left: 8px solid {warn_border};
}
QLabel[badge="true"][badgeKind="danger"] {
  border-left: 8px solid {danger_border};
}
QLabel[badge="true"][badgeKind="muted"] {
  border-left: 8px solid @BORDER_DIMMER@;
}
QLabel[badge="true"][badgeKind="accent"] {
  border-left: 8px solid @ACCENT_BORDER@;
}

/* ---------- Mid-state card ---------- */
QWidget#midState {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_DIM@;
  border-radius: @RADIUS_LG@;
}
QWidget#midState[pulse="true"] {
  border-bottom: 2px solid rgba(96, 165, 250, 0.65);
}
QWidget#midState[pulse="false"] {
  border-bottom: 2px solid rgba(96, 165, 250, 0.0);
}

QLabel[badge="true"][pulse="true"] {
  border-left: 8px solid rgba(96, 165, 250, 0.90);
}

/* ---------- Video overlay ---------- */
QWidget#videoOverlay {
  background: @OVERLAY_BG@;
  border: 1px solid @BORDER_SOFT@;
  border-radius: @RADIUS_LG@;
}

/* ---------- Fade overlay (layout transitions) ---------- */
QWidget#fadeOverlay {
  background: rgba(15, 23, 42, 255);
  border: none;
}

/* ---------- Modal overlay (confirm exit, etc.) ---------- */
QWidget#modalOverlay {
  background: @OVERLAY_BG@;
  border: none;
}
QWidget#modalCard {
  background: @MENU_BG@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_LG@;
}
QWidget#modalCard[risk="true"] {
  /* High-salience confirm: danger accent without screaming */
  border: 1px solid rgba(248, 113, 113, 0.55);
  background: rgba(11, 18, 32, 0.92);
}
QWidget#modalCard[risk="false"] {
  border: 1px solid rgba(96, 165, 250, 0.45);
}
QLabel#modalTitle {
  font-size: @FONT_H2@;
  font-weight: 900;
  color: @TEXT_STRONG@;
}
QLabel#modalBody {
  color: @TEXT@;
}
QLabel#videoOverlayTitle {
  font-size: @FONT_LABEL@;
  font-weight: 800;
  color: @TEXT_STRONG@;
}

/* ---------- Drive guard overlay (connect-first) ---------- */
QWidget#driveGuardOverlay {
  background: rgba(2, 6, 23, 0.78);
  border: 1px solid @BORDER_SOFT@;
  border-radius: @RADIUS_LG@;
}
QLabel#driveGuardTitle {
  font-size: @FONT_H2@;
  font-weight: 900;
  color: @TEXT_STRONG@;
}

/* ---------- Progress (Racing HUD) ---------- */
QProgressBar {
  background: rgba(2, 6, 23, 0.28);
  border: 1px solid @BORDER_SOFT@;
  border-radius: @RADIUS_MD@;
  height: 10px;
}
QProgressBar[busy="false"] {
  background: transparent;
  border: none;
}
QProgressBar::chunk {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 rgba(147, 197, 253, 0.85),
    stop:1 @ACCENT_70@
  );
  border-radius: @RADIUS_MD@;
}
QProgressBar[busy="false"]::chunk {
  background: transparent;
}

/* ---------- Splash ---------- */
QWidget#splashRoot {
  background: @SPLASH_BG@;
  border: 1px solid @BORDER@;
  border-radius: 18px;
}
QLabel#splashTitle {
  color: @TEXT_STRONG@;
}
QProgressBar#splashProgress {
  background: @BORDER_SOFT@;
  border: 1px solid @BORDER@;
  border-radius: @RADIUS_MD@;
}
QProgressBar#splashProgress::chunk {
  background: @ACCENT_85@;
  border-radius: @RADIUS_MD@;
}
QProgressBar[barKind="gas"]::chunk {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 @GAS_STOP0@,
    stop:1 @GAS_STOP1@
  );
}
QProgressBar[barKind="brake"]::chunk {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 @BRAKE_STOP0@,
    stop:1 @BRAKE_STOP1@
  );
}
QProgressBar[barKind="steer"]::chunk {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 @STEER_STOP0@,
    stop:1 @STEER_STOP1@
  );
  border-left: 2px solid rgba(2, 6, 23, 0.55);
  border-right: 2px solid rgba(2, 6, 23, 0.55);
}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {
  background: transparent;
  width: 10px;
  margin: 2px;
}
QScrollBar::handle:vertical {
  background: @SCROLLBAR_HANDLE@;
  border-radius: @RADIUS_MD@;
  min-height: 20px;
}
QScrollBar::handle:vertical:hover {
  background: @SCROLLBAR_HANDLE_HOVER@;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
  height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
  background: transparent;
}

QScrollBar:horizontal {
  background: transparent;
  height: 10px;
  margin: 2px;
}
QScrollBar::handle:horizontal {
  background: @SCROLLBAR_HANDLE@;
  border-radius: @RADIUS_MD@;
  min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
  background: @SCROLLBAR_HANDLE_HOVER@;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
  width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
  background: transparent;
}

/* Premium: keep scrollbars subtle until hover */
QAbstractScrollArea::corner {
  background: transparent;
}

/* ---------- Cards (premium surfaces) ---------- */
QWidget[card="true"] {
  background: @SURFACE_WEAK@;
  border: 1px solid @BORDER_DIM@;
  border-radius: @RADIUS_LG@;
}
QWidget[card="true"]:hover {
  border: 1px solid @BORDER_HOVER@;
  background: @SURFACE@;
}
"""

    return (
        qss.replace("@BG@", bg)
        .replace("@TEXT@", text)
        .replace("@TEXT_STRONG@", text_strong)
        .replace("@MUTED@", muted)
        .replace("@BORDER@", border)
        .replace("@BORDER_SOFT@", border_soft)
        .replace("@BORDER_DIM@", border_dim)
        .replace("@BORDER_DIMMER@", border_dimmer)
        .replace("@BORDER_HOVER@", border_hover)
        .replace("@BORDER_PRESSED@", border_pressed)
        .replace("@TEXT_DISABLED@", text_disabled)
        .replace("@BORDER_DISABLED@", border_disabled)
        .replace("@FILL_HOVER@", fill_hover)
        .replace("@TITLE_BG@", title_bg)
        .replace("@SURFACE_DISABLED@", surface_disabled)
        .replace("@TOOLTIP_BG@", tooltip_bg)
        .replace("@MENU_BG@", menu_bg)
        .replace("@SURFACE_WEAK@", surface_weak)
        .replace("@SURFACE@", surface)
        .replace("@SURFACE_STRONG@", surface_strong)
        .replace("@BUTTON_TOP@", button_top)
        .replace("@BUTTON_BOTTOM@", button_bottom)
        .replace("@BUTTON_HOVER_TOP@", button_hover_top)
        .replace("@BUTTON_HOVER_BOTTOM@", button_hover_bottom)
        .replace("@BUTTON_PRESSED_TOP@", button_pressed_top)
        .replace("@BUTTON_PRESSED_BOTTOM@", button_pressed_bottom)
        .replace("@BANNER_BG@", banner_bg)
        .replace("@CHIP_BG@", chip_bg)
        .replace("@PROGRESS_BG@", progress_bg)
        .replace("@SPLASH_BG@", splash_bg)
        .replace("@SCROLLBAR_HANDLE@", scrollbar_handle)
        .replace("@SCROLLBAR_HANDLE_HOVER@", scrollbar_handle_hover)
        .replace("@ACCENT_10@", accent_10)
        .replace("@ACCENT_16@", accent_16)
        .replace("@ACCENT_22@", accent_22)
        .replace("@ACCENT_35@", accent_35)
        .replace("@ACCENT_60@", accent_60)
        .replace("@ACCENT_65@", accent_65)
        .replace("@ACCENT_70@", accent_70)
        .replace("@ACCENT_85@", accent_85)
        .replace("@ACCENT_SOLID@", accent_solid)
        .replace("@ACCENT_BORDER@", accent_border)
        .replace("@OK_TEXT@", ok_text)
        .replace("@WARN_TEXT@", warn_text)
        .replace("@DANGER_TEXT@", danger_text)
        .replace("@MUTED_TEXT@", muted_text)
        .replace("@ACCENT_TEXT@", accent_text)
        .replace("@CHECKED_STOP0@", checked_stop0)
        .replace("@CHECKED_STOP1@", checked_stop1)
        .replace("@PRIMARY_TEXT@", primary_text)
        .replace("@PRIMARY_STOP0@", primary_stop0)
        .replace("@PRIMARY_STOP1@", primary_stop1)
        .replace("@PRIMARY_BORDER@", primary_border)
        .replace("@PRIMARY_HOVER_STOP0@", primary_hover_stop0)
        .replace("@PRIMARY_HOVER_STOP1@", primary_hover_stop1)
        .replace("@PRIMARY_HOVER_BORDER@", primary_hover_border)
        .replace("@PRIMARY_PRESSED_STOP0@", primary_pressed_stop0)
        .replace("@PRIMARY_PRESSED_STOP1@", primary_pressed_stop1)
        .replace("@PRIMARY_PRESSED_BORDER@", primary_pressed_border)
        .replace("@DANGER_TEXT_BTN@", danger_text_btn)
        .replace("@DANGER_STOP0@", danger_stop0)
        .replace("@DANGER_STOP1@", danger_stop1)
        .replace("@DANGER_BORDER_BTN@", danger_border_btn)
        .replace("@DANGER_HOVER_STOP0@", danger_hover_stop0)
        .replace("@DANGER_HOVER_STOP1@", danger_hover_stop1)
        .replace("@DANGER_HOVER_BORDER@", danger_hover_border)
        .replace("@DANGER_PRESSED_STOP0@", danger_pressed_stop0)
        .replace("@DANGER_PRESSED_STOP1@", danger_pressed_stop1)
        .replace("@DANGER_PRESSED_BORDER@", danger_pressed_border)
        .replace("@GAS_STOP0@", gas_stop0)
        .replace("@GAS_STOP1@", gas_stop1)
        .replace("@BRAKE_STOP0@", brake_stop0)
        .replace("@BRAKE_STOP1@", brake_stop1)
        .replace("@STEER_STOP0@", steer_stop0)
        .replace("@STEER_STOP1@", steer_stop1)
        .replace("@RADIUS_MD@", radius_md)
        .replace("@RADIUS_LG@", radius_lg)
        .replace("@PAD_SM@", pad_sm)
        .replace("@PAD_MD@", pad_md)
        .replace("@PAD_BTN@", pad_btn)
        .replace("@PAD_CHIP@", pad_chip)
        .replace("@PAD_ICON@", pad_icon)
        .replace("@BTN_MIN_H@", btn_min_h)
        .replace("@BADGE_MIN_H@", badge_min_h)
        .replace("@LIST_PAD@", list_pad)
        .replace("@OVERLAY_BG@", overlay_bg)
        .replace("@FONT_BASE@", font_base)
        .replace("@FONT_TITLE@", font_title)
        .replace("@FONT_LABEL@", font_label)
        .replace("@FONT_MONO@", font_mono)
        .replace("@FONT_H2@", font_h2)
        .replace("@OK_FILL@", ok_fill)
        .replace("@WARN_FILL@", warn_fill)
        .replace("@DANGER_FILL@", danger_fill)
        .replace("@MUTED_FILL@", muted_fill)
        .replace("@ACCENT_FILL@", accent_fill)
        .replace("{ok_border}", ok_border)
        .replace("{warn_border}", warn_border)
        .replace("{danger_border}", danger_border)
    )
