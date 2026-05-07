from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QComboBox, QLabel,
)

from manager import DeviceManager
from ui.device_table import DeviceTable
from ui.mass_actions import MassActionsPanel
from ui.device_detail import DeviceDetailPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sennheiser IEM G4 Control")
        self.resize(950, 650)

        self._manager = DeviceManager(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Interface:"))
        self._iface_combo = QComboBox()
        self._iface_combo.setMinimumWidth(200)
        self._populate_interfaces()
        toolbar.addWidget(self._iface_combo)

        self._scan_btn = QPushButton("Scan Network")
        self._scan_btn.clicked.connect(self._on_scan)
        toolbar.addWidget(self._scan_btn)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Device table
        self._table = DeviceTable()
        layout.addWidget(self._table, stretch=3)

        # Mass actions
        self._mass_panel = MassActionsPanel()
        layout.addWidget(self._mass_panel)

        # Device detail
        self._detail = DeviceDetailPanel()
        layout.addWidget(self._detail, stretch=2)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready. Click 'Scan Network' to discover devices.")

        self._connect_signals()

    def _connect_signals(self):
        # Manager signals
        self._manager.device_discovered.connect(self._on_device_discovered)
        self._manager.device_updated.connect(self._on_device_updated)
        self._manager.device_went_offline.connect(self._on_device_updated)
        self._manager.device_came_online.connect(self._on_device_updated)
        self._manager.scan_finished.connect(self._on_scan_finished)

        # Table signals
        self._table.device_selected.connect(self._on_device_selected)
        self._table.selection_changed.connect(self._on_checked_changed)

        # Mass action signals
        self._mass_panel.sensitivity_apply.connect(self._on_mass_sensitivity)
        self._mass_panel.mute_all.connect(self._on_mass_mute)
        self._mass_panel.unmute_all.connect(self._on_mass_unmute)

        # Detail panel -> Manager
        self._detail.name_changed.connect(self._manager.set_name)
        self._detail.frequency_changed.connect(self._manager.set_frequency)
        self._detail.sensitivity_changed.connect(self._manager.set_sensitivity)
        self._detail.mode_changed.connect(self._manager.set_mode)
        self._detail.mute_changed.connect(self._manager.set_mute)
        self._detail.eq_changed.connect(self._manager.set_equalizer)

    def _populate_interfaces(self):
        self._iface_combo.clear()
        ifaces = DeviceManager.get_interfaces()
        for iface in ifaces:
            label = f"{iface['name']} — {iface['ip']}/{iface['mask']}"
            self._iface_combo.addItem(label, iface)

    def _on_scan(self):
        self._scan_btn.setEnabled(False)
        iface = self._iface_combo.currentData()
        subnet = f"{iface['ip']}/{iface['mask']}" if iface else "unknown"
        self._status.showMessage(f"Scanning {subnet}...")
        self._table.clear_all()
        self._detail.setVisible(False)
        self._manager.clear_devices()
        self._manager.start_scan(iface)

    def _on_refresh(self):
        for ip in self._manager.devices:
            self._manager._query_all_params(ip)

    def _on_scan_finished(self):
        self._scan_btn.setEnabled(True)
        count = len(self._manager.devices)
        self._status.showMessage(f"Scan complete. Found {count} device(s).")

    def _on_device_discovered(self, ip: str):
        device = self._manager.devices[ip]
        self._table.add_device(device)
        self._status.showMessage(f"Found: {ip}")

    def _on_device_updated(self, ip: str):
        device = self._manager.devices.get(ip)
        if device:
            self._table.update_device(device)
            self._detail.update_levels(device)

    def _on_device_selected(self, ip: str):
        device = self._manager.devices.get(ip)
        if device:
            self._detail.show_device(device)

    def _on_checked_changed(self, ips: list[str]):
        self._mass_panel.update_selection_count(len(ips))

    def _on_mass_sensitivity(self, value: int):
        ips = self._table.get_checked_ips()
        self._manager.mass_set_sensitivity(ips, value)

    def _on_mass_mute(self):
        ips = self._table.get_checked_ips()
        self._manager.mass_set_mute(ips, True)

    def _on_mass_unmute(self):
        ips = self._table.get_checked_ips()
        self._manager.mass_set_mute(ips, False)
