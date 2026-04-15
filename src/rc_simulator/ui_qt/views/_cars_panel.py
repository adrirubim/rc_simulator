from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ...core.models import Car
from ..strings import UI


@dataclass(slots=True, weakref_slot=True)
class CarsPanel:
    cfg: object
    search: QLineEdit
    list_widget: QListWidget
    list_hint: QLabel
    get_cars: Callable[[], list[Car]]
    get_active_car_id: Callable[[], str | None]
    set_filtered_indices: Callable[[list[int]], None]
    set_selected_index: Callable[[int | None], None]
    get_filtered_indices: Callable[[], list[int]]
    get_selected_index: Callable[[], int | None]
    on_selection_changed: Callable[[], None]
    on_after_filter_applied: Callable[[], None]
    get_preferred_ip: Callable[[], str | None] | None = None
    _car_filter_debounce_seq: int = field(default=0, init=False)
    _last_filter_query: str = field(default="", init=False)
    _last_filter_signature: tuple | None = field(default=None, init=False)
    _last_filter_active_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        return

    def apply_car_filter(self) -> None:
        cars = self.get_cars()
        q = (self.search.text() or "").strip().lower()

        # Debounce optimization: avoid rebuilding if filter inputs didn't change.
        try:
            sig = tuple((str(c.car_id), str(c.name), str(c.ip), int(c.control_port)) for c in cars)
        except Exception:
            sig = None
        active_car_id = str(self.get_active_car_id() or "")
        if (
            q == self._last_filter_query
            and sig == self._last_filter_signature
            and active_car_id == self._last_filter_active_id
        ):
            return
        self._last_filter_query = q
        self._last_filter_signature = sig
        self._last_filter_active_id = active_car_id

        # Preserve operator selection where possible.
        # Prefer the currently selected row's IP (UI truth), then active_car_id (session truth).
        desired_ip: str | None = None
        try:
            rows = self.list_widget.selectedIndexes()
            if rows:
                cur_item = self.list_widget.item(rows[0].row())
                cur_row = self.list_widget.itemWidget(cur_item) if cur_item is not None else None
                if cur_row is not None:
                    for child in cur_row.findChildren(QLabel):
                        if child.objectName() == "muted":
                            desired_ip = (child.text() or "").split(":")[0].strip() or None
                            break
        except Exception:
            desired_ip = None
        if desired_ip is None:
            desired_ip = str(self.get_active_car_id() or "").strip() or None
        if desired_ip is None and callable(self.get_preferred_ip):
            try:
                desired_ip = str(self.get_preferred_ip() or "").strip() or None
            except Exception:
                desired_ip = None

        self.list_widget.clear()
        filtered_indices: list[int] = []
        preferred_row: int | None = None

        for idx, car in enumerate(cars):
            hay = f"{car.name} {car.ip} {car.control_port}".lower()
            if q and q not in hay:
                continue
            filtered_indices.append(idx)
            item = QListWidgetItem(self.list_widget)
            # Two-line rich row
            row = QWidget(self.list_widget)
            row.setObjectName("carRow")
            ip = str(car.ip or "")
            row.setProperty("active", "true" if (active_car_id and ip == active_car_id) else "false")
            rl = QVBoxLayout(row)
            density = str(getattr(self.cfg, "density", "comfortable"))
            if density == "compact":
                rl.setContentsMargins(8, 6, 8, 6)
            else:
                rl.setContentsMargins(10, 8, 10, 8)
            rl.setSpacing(2)
            title_row = QWidget(row)
            tr_l = QHBoxLayout(title_row)
            tr_l.setContentsMargins(0, 0, 0, 0)
            tr_l.setSpacing(8)

            title = QLabel(str(car.name), title_row)
            title.setObjectName("carTitle")
            tr_l.addWidget(title, 1)

            connected_pill = QLabel(UI.badge_connected, title_row)
            connected_pill.setObjectName("carConnectedPill")
            connected_pill.setProperty("badge", True)
            connected_pill.setProperty("badgeKind", "ok")
            connected_pill.setVisible(bool(active_car_id and ip == active_car_id))
            tr_l.addWidget(connected_pill, 0)

            subtitle = QLabel(f"{car.ip}:{car.control_port}", row)
            subtitle.setObjectName("muted")
            rl.addWidget(title_row)
            rl.addWidget(subtitle)
            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

            if preferred_row is None and desired_ip and ip and ip == desired_ip:
                preferred_row = self.list_widget.count() - 1

        self.set_filtered_indices(filtered_indices)

        if filtered_indices:
            row = int(preferred_row) if preferred_row is not None else 0
            self.list_widget.setCurrentRow(row)
            self.set_selected_index(row)
        else:
            self.set_selected_index(None)
            # Keep the list clean; the mid-state card and hint already explain what to do.
            self.list_widget.clearSelection()

        self.on_after_filter_applied()

    def refresh_car_row_active_styles(self) -> None:
        # Update row properties in-place without rebuilding the list.
        active = str(self.get_active_car_id() or "")
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item is None:
                continue
            row = self.list_widget.itemWidget(item)
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
            try:
                for child in row.findChildren(QLabel):
                    if child.objectName() == "carConnectedPill":
                        child.setVisible(kind == "true")
                        break
            except Exception:
                pass

    def debounce_apply_car_filter(self) -> None:
        self._car_filter_debounce_seq += 1
        seq = int(self._car_filter_debounce_seq)

        def _apply_if_latest() -> None:
            if seq != self._car_filter_debounce_seq:
                return
            self.apply_car_filter()

        QTimer.singleShot(150, _apply_if_latest)

    def on_select(self) -> None:
        rows = self.list_widget.selectedIndexes()
        if not rows:
            return
        self.set_selected_index(rows[0].row())
        self.on_selection_changed()
