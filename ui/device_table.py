from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt

from device import IEMDevice


COLUMNS = ["", "Name", "IP", "Frequency", "Sensitivity", "Mute", "Mode"]


class DeviceTable(QTableWidget):
    device_selected = pyqtSignal(str)       # ip of clicked device
    selection_changed = pyqtSignal(list)     # list of checked IPs
    device_identify_requested = pyqtSignal(str)   # ip — wired in Task 7

    def __init__(self, parent=None):
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 30)
        for i in range(1, len(COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self.cellClicked.connect(self._on_cell_clicked)
        self._ip_to_row: dict[str, int] = {}

    def add_device(self, device: IEMDevice):
        if device.ip in self._ip_to_row:
            return
        row = self.rowCount()
        self.insertRow(row)
        self._ip_to_row[device.ip] = row

        cb = QCheckBox()
        cb.stateChanged.connect(lambda _: self._emit_checked_ips())
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(cb)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setCellWidget(row, 0, container)

        self.setItem(row, 1, QTableWidgetItem(device.name))
        self.setItem(row, 2, QTableWidgetItem(device.ip))
        self.setItem(row, 3, QTableWidgetItem(device.frequency_mhz))
        self.setItem(row, 4, QTableWidgetItem(str(device.sensitivity)))
        self.setItem(row, 5, QTableWidgetItem("On" if device.mute else "Off"))
        self.setItem(row, 6, QTableWidgetItem(device.mode.capitalize()))

    def update_device(self, device: IEMDevice):
        row = self._ip_to_row.get(device.ip)
        if row is None:
            return

        for col, text in [(1, device.name), (3, device.frequency_mhz),
                          (4, str(device.sensitivity)),
                          (5, "On" if device.mute else "Off"),
                          (6, device.mode.capitalize())]:
            item = self.item(row, col)
            if item:
                item.setText(text)

        for col in range(1, len(COLUMNS)):
            item = self.item(row, col)
            if item:
                if not device.online:
                    item.setForeground(Qt.GlobalColor.darkGray)

    def get_checked_ips(self) -> list[str]:
        ips = []
        for ip, row in self._ip_to_row.items():
            container = self.cellWidget(row, 0)
            cb = container.findChild(QCheckBox)
            if cb and cb.isChecked():
                ips.append(ip)
        return ips

    def clear_all(self):
        self.setRowCount(0)
        self._ip_to_row.clear()

    def _on_cell_clicked(self, row, _col):
        for ip, r in self._ip_to_row.items():
            if r == row:
                self.device_selected.emit(ip)
                return

    def _emit_checked_ips(self):
        self.selection_changed.emit(self.get_checked_ips())

    def select_all(self):
        self._set_all_checked(True)

    def clear_selection(self):
        self._set_all_checked(False)

    def _set_all_checked(self, checked: bool):
        for ip in self._ip_to_row:
            row = self._ip_to_row[ip]
            container = self.cellWidget(row, 0)
            if container:
                cb = container.findChild(QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(checked)
                    cb.blockSignals(False)
        self._emit_checked_ips()
