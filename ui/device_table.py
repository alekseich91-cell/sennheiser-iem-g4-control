from PyQt6.QtCore import pyqtSignal, Qt, QSettings, QTimer
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QWidget, QHBoxLayout, QPushButton,
)

from device import IEMDevice


COL_CHECK, COL_NAME, COL_IP, COL_FREQ, COL_SENS, COL_RF, COL_LOCK, COL_MUTE, COL_MODE, COL_ONLINE, COL_IDENT = range(11)
COLUMNS = ["", "Name", "IP", "Frequency", "Sensitivity", "RF", "Lock", "Mute", "Mode", "Online", ""]


class DeviceTable(QTableWidget):
    selection_changed = pyqtSignal(list)
    device_identify_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)

        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_CHECK, 30)
        header.setSectionResizeMode(COL_IDENT, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_IDENT, 50)
        for i in range(1, len(COLUMNS) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        # Restore sort order from QSettings
        settings = QSettings("SennheiserIEMControl", "DeviceTable")
        col = settings.value("table/sortColumn", -1, type=int)
        order_int = settings.value("table/sortOrder", 0, type=int)
        if col >= 0:
            order = Qt.SortOrder.AscendingOrder if order_int == 0 else Qt.SortOrder.DescendingOrder
            self.sortItems(col, order)
        header.sortIndicatorChanged.connect(self._on_sort_changed)

        self._ip_to_row: dict[str, int] = {}
        self._af_peak_timers: dict[str, QTimer] = {}

    # --- Public ---

    def add_device(self, device: IEMDevice):
        if device.ip in self._ip_to_row:
            return
        was_sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)

        row = self.rowCount()
        self.insertRow(row)
        self._ip_to_row[device.ip] = row

        cb = QCheckBox()
        cb.stateChanged.connect(lambda _: self._emit_checked_ips())
        container = QWidget()
        cb_layout = QHBoxLayout(container)
        cb_layout.addWidget(cb)
        cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        self.setCellWidget(row, COL_CHECK, container)

        ident_btn = QPushButton("💡")
        ident_btn.setFixedWidth(40)
        ident_btn.clicked.connect(lambda _, ip=device.ip: self.device_identify_requested.emit(ip))
        ident_container = QWidget()
        ident_layout = QHBoxLayout(ident_container)
        ident_layout.addWidget(ident_btn)
        ident_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ident_layout.setContentsMargins(0, 0, 0, 0)
        self.setCellWidget(row, COL_IDENT, ident_container)

        self.setItem(row, COL_NAME, QTableWidgetItem(device.name))
        self.setItem(row, COL_IP, QTableWidgetItem(device.ip))
        self.setItem(row, COL_FREQ, QTableWidgetItem(device.frequency_mhz))
        self.setItem(row, COL_SENS, QTableWidgetItem(str(device.sensitivity)))
        self.setItem(row, COL_RF, QTableWidgetItem(device.rf_power))
        self.setItem(row, COL_LOCK, QTableWidgetItem("🔒" if device.panel_locked else ""))
        self.setItem(row, COL_MUTE, QTableWidgetItem("On" if device.mute else "Off"))
        self.setItem(row, COL_MODE, QTableWidgetItem(device.mode.capitalize()))
        self.setItem(row, COL_ONLINE, QTableWidgetItem("●" if device.online else "○"))

        self._apply_row_colors(device)
        self.setSortingEnabled(was_sorting)

    def update_device(self, device: IEMDevice):
        row = self._row_for_ip(device.ip)
        if row is None:
            return

        was_sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)

        for col, text in [
            (COL_NAME, device.name),
            (COL_FREQ, device.frequency_mhz),
            (COL_SENS, str(device.sensitivity)),
            (COL_RF, device.rf_power),
            (COL_LOCK, "🔒" if device.panel_locked else ""),
            (COL_MUTE, "On" if device.mute else "Off"),
            (COL_MODE, device.mode.capitalize()),
            (COL_ONLINE, "●" if device.online else "○"),
        ]:
            item = self.item(row, col)
            if item:
                item.setText(text)

        self._apply_row_colors(device)
        self.setSortingEnabled(was_sorting)

    def get_checked_ips(self) -> list[str]:
        ips = []
        for ip in self._ip_to_row:
            row = self._row_for_ip(ip)
            if row is None:
                continue
            container = self.cellWidget(row, COL_CHECK)
            cb = container.findChild(QCheckBox) if container else None
            if cb and cb.isChecked():
                ips.append(ip)
        return ips

    def clear_all(self):
        self.setRowCount(0)
        self._ip_to_row.clear()
        for t in self._af_peak_timers.values():
            t.stop()
        self._af_peak_timers.clear()

    def select_all(self):
        self._set_all_checked(True)

    def clear_selection(self):
        self._set_all_checked(False)

    def _set_all_checked(self, checked: bool):
        for ip in list(self._ip_to_row.keys()):
            row = self._row_for_ip(ip)
            if row is None:
                continue
            container = self.cellWidget(row, COL_CHECK)
            cb = container.findChild(QCheckBox) if container else None
            if cb:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)
        self._emit_checked_ips()

    def flash_af_peak(self, ip: str):
        row = self._row_for_ip(ip)
        if row is None:
            return
        for col in range(1, len(COLUMNS) - 1):
            item = self.item(row, col)
            if item:
                item.setBackground(QBrush(QColor("#fff3a8")))
        timer = self._af_peak_timers.get(ip)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda ip=ip: self._clear_af_peak(ip))
            self._af_peak_timers[ip] = timer
        timer.start(200)

    # --- Internal ---

    def _row_for_ip(self, ip: str) -> int | None:
        for r in range(self.rowCount()):
            item = self.item(r, COL_IP)
            if item and item.text() == ip:
                return r
        return None

    def _apply_row_colors(self, device: IEMDevice):
        row = self._row_for_ip(device.ip)
        if row is None:
            return
        for col in range(1, len(COLUMNS) - 1):
            item = self.item(row, col)
            if not item:
                continue
            if device.mute:
                item.setBackground(QBrush(QColor("#dddddd")))
            else:
                item.setBackground(QBrush())
            if not device.online:
                item.setForeground(QBrush(QColor("#cc0000")))
            else:
                item.setForeground(QBrush())

    def _clear_af_peak(self, ip: str):
        row = self._row_for_ip(ip)
        if row is None:
            return
        for col in range(1, len(COLUMNS) - 1):
            item = self.item(row, col)
            if item:
                item.setBackground(QBrush())

    def _on_sort_changed(self, col: int, order: Qt.SortOrder):
        settings = QSettings("SennheiserIEMControl", "DeviceTable")
        settings.setValue("table/sortColumn", col)
        settings.setValue("table/sortOrder", 0 if order == Qt.SortOrder.AscendingOrder else 1)

    def _emit_checked_ips(self):
        self.selection_changed.emit(self.get_checked_ips())
