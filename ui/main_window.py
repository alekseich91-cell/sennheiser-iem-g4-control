import datetime

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QComboBox, QLabel, QFileDialog,
)

from manager import DeviceManager
from ui.device_table import DeviceTable
from ui.control_panel import ControlPanel
from app_log import collected_log_paths, log_dir


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sennheiser IEM G4 Control")
        self.resize(1100, 750)

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

        # Unified control panel
        self._panel = ControlPanel()
        layout.addWidget(self._panel, stretch=2)

        # Help menu
        menu = self.menuBar().addMenu("Help")
        export_act = QAction("Export Logs…", self)
        export_act.triggered.connect(self._on_export_logs)
        menu.addAction(export_act)
        show_folder_act = QAction("Show Log Folder", self)
        show_folder_act.triggered.connect(self._on_show_log_folder)
        menu.addAction(show_folder_act)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready. Click 'Scan Network' to discover devices.")

        self._connect_signals()

    def _connect_signals(self):
        self._manager.device_discovered.connect(self._on_device_discovered)
        self._manager.device_updated.connect(self._on_device_updated)
        self._manager.device_went_offline.connect(self._on_device_updated)
        self._manager.device_came_online.connect(self._on_device_updated)
        self._manager.scan_finished.connect(self._on_scan_finished)

        self._table.selection_changed.connect(self._on_selection_changed)
        self._table.device_identify_requested.connect(self._manager.identify)

        self._panel.name_changed.connect(self._manager.set_name)
        self._panel.frequency_changed.connect(self._manager.set_frequency)
        self._panel.sensitivity_changed.connect(self._manager.set_sensitivity)
        self._panel.mode_changed.connect(self._manager.set_mode)
        self._panel.mute_changed.connect(self._manager.set_mute)
        self._panel.eq_changed.connect(self._manager.set_equalizer)
        self._panel.rf_power_changed.connect(self._manager.set_rf_power)
        self._panel.panel_lock_changed.connect(self._manager.set_panel_lock)

        self._panel.identify_selected.connect(self._manager.mass_identify)
        self._panel.reset_selected.connect(self._manager.mass_reset)
        self._panel.apply_pending.connect(self._on_apply_pending)

        self._panel.select_all_btn.clicked.connect(self._table.select_all)
        self._panel.clear_btn.clicked.connect(self._table.clear_selection)

        self._panel.mute_all_btn.clicked.connect(self._manager.mute_all)
        self._panel.unmute_all_btn.clicked.connect(self._manager.unmute_all)
        self._panel.identify_all_btn.clicked.connect(self._manager.identify_all)

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
        self._panel.set_selection([])
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
        self._panel.set_devices(self._manager.devices)
        self._status.showMessage(f"Found: {ip}")

    def _on_device_updated(self, ip: str):
        device = self._manager.devices.get(ip)
        if device:
            self._table.update_device(device)
            self._panel.set_devices(self._manager.devices)
            self._panel.update_levels(ip)

    def _on_selection_changed(self, ips: list[str]):
        self._panel.set_devices(self._manager.devices)
        self._panel.set_selection(ips)

    def _on_apply_pending(self, ips: list[str], pending: dict):
        if "sensitivity" in pending:
            self._manager.mass_set_sensitivity(ips, pending["sensitivity"])
        if "mode" in pending:
            self._manager.mass_set_mode(ips, pending["mode"])
        if "rf_power" in pending:
            self._manager.mass_set_rf_power(ips, pending["rf_power"])
        if "panel_locked" in pending:
            self._manager.mass_set_panel_lock(ips, pending["panel_locked"])
        if "mute" in pending:
            self._manager.mass_set_mute(ips, pending["mute"])
        if "eq" in pending:
            enabled, bands = pending["eq"]
            self._manager.mass_set_eq(ips, enabled, bands)
        self._status.showMessage(f"Applied changes to {len(ips)} device(s).")

    def _on_export_logs(self):
        default_name = f"iem-log-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Export Logs", default_name, "Text (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as out:
            for src in collected_log_paths():
                out.write(f"=== {src.name} ===\n")
                try:
                    out.write(src.read_text(encoding="utf-8", errors="replace"))
                except OSError as e:
                    out.write(f"<failed to read: {e}>\n")
                out.write("\n")
        self._status.showMessage(f"Logs exported to {path}")

    def _on_show_log_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir())))
