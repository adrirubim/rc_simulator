from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPlainTextEdit, QPushButton, QScrollBar

from ..strings import UI


@dataclass(slots=True, weakref_slot=True)
class LogPanel:
    cfg: object
    log_filter: object
    log_view: QPlainTextEdit
    btn_pause_log: QPushButton
    level_to_kind: Callable[[str], str]
    standard_icon: Callable[[int], QIcon]
    sp_media_pause: int
    sp_media_play: int
    enforce_widget_limit: int = 500
    log_store: list[tuple[str, str, str]] = field(default_factory=list, init=False)  # (ts, level, text)
    _log_auto_paused: bool = field(default=False, init=False)
    _log_last_render_was_filtered: bool = field(default=False, init=False)
    _log_scrollbar: QScrollBar | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._log_scrollbar = self.log_view.verticalScrollBar()
        self._log_scrollbar.valueChanged.connect(self._on_log_scroll_changed)
        # Hard cap on visible lines for performance (Qt handles trimming efficiently).
        try:
            self.log_view.setMaximumBlockCount(int(self.enforce_widget_limit))
        except Exception:
            pass

    def _fmt_line(self, ts: str, lvl: str, txt: str) -> str:
        return f"{ts}  {lvl:<5} {txt}"

    def append_log(self, level: str, text: str) -> None:
        lvl = (level or "INFO").upper()
        ts = time.strftime("%H:%M:%S")
        self.log_store.append((ts, lvl, str(text)))
        # Fast-path: if not filtered and not paused, append incrementally (avoids rebuilding the whole list).
        if (not (self.log_filter.text() or "").strip()) and (not self.btn_pause_log.isChecked()):
            self._log_last_render_was_filtered = False
            self._append_line(ts, lvl, str(text), follow_tail=True)
            # keep store bounded
            max_lines = int(getattr(self.cfg, "log_max_lines", 5000))
            if len(self.log_store) > max_lines:
                self.log_store[:] = self.log_store[-max_lines:]
        else:
            self.refresh_log_view()

    def append_logs(self, items: list[tuple[str, str]]) -> None:
        """
        Batched log append to keep UI fluid under bursts.

        items: [(level, message), ...]
        """
        if not items:
            return

        ts = time.strftime("%H:%M:%S")
        # Update store first (bounded once per batch).
        for level, text in items:
            lvl = (level or "INFO").upper()
            self.log_store.append((ts, lvl, str(text)))
        max_lines = int(getattr(self.cfg, "log_max_lines", 5000))
        if len(self.log_store) > max_lines:
            self.log_store[:] = self.log_store[-max_lines:]

        # Fast-path: if not filtered and not paused, append once (single widget update).
        if (not (self.log_filter.text() or "").strip()) and (not self.btn_pause_log.isChecked()):
            self._log_last_render_was_filtered = False
            try:
                sb = self.log_view.verticalScrollBar()
                at_bottom_before = sb.value() >= (sb.maximum() - 2)
            except Exception:
                at_bottom_before = True

            lines: list[str] = []
            for level, text in items:
                lvl = (level or "INFO").upper()
                lines.append(self._fmt_line(ts, lvl, str(text)))
            try:
                # One append to reduce per-line overhead.
                self.log_view.appendPlainText("\n".join(lines))
            except Exception:
                pass
            if at_bottom_before:
                self._scroll_to_bottom()
            return

        # If filtered or paused, rebuild for correctness.
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
        max_lines = int(getattr(self.cfg, "log_max_lines", 5000))
        out_lines: list[str] = []
        for ts, lvl, txt in self.log_store[-max_lines:]:
            line = self._fmt_line(ts, lvl, txt)
            if f and f not in line.lower():
                continue
            out_lines.append(line)

        if out_lines:
            self.log_view.setPlainText("\n".join(out_lines))
        else:
            # Premium empty-state: keep the dashboard feeling intentional.
            if not f:
                self.log_view.setPlainText(UI.log_empty_placeholder)
            else:
                self.log_view.setPlainText("")

        if was_paused:
            # preserve reading position
            sb.setValue(min(prev_val, sb.maximum()))
        else:
            # keep up with live tail unless user scrolled up
            if at_bottom_before:
                self._scroll_to_bottom()

    def on_pause_toggled(self, paused: bool) -> None:
        self.btn_pause_log.setText(UI.log_resume if paused else UI.log_pause)
        self.btn_pause_log.setIcon(self.standard_icon(self.sp_media_play if paused else self.sp_media_pause))
        if not paused:
            self._log_auto_paused = False
            self._scroll_to_bottom()

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

    def _scroll_to_bottom(self) -> None:
        try:
            sb = self.log_view.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            pass

    def _append_line(self, ts: str, lvl: str, txt: str, *, follow_tail: bool) -> None:
        self.log_view.appendPlainText(self._fmt_line(ts, lvl, txt))
        if follow_tail:
            self._scroll_to_bottom()
