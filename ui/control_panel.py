from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QSlider, QComboBox, QPushButton, QProgressBar,
    QGroupBox, QCheckBox, QFrame,
)

from device import IEMDevice


EQ_BANDS = ["Low", "Low Mid", "Mid", "Mid High", "High"]
RF_LEVELS = ["Lo", "Std", "Hi"]


class ControlPanel(QWidget):
    """Unified panel that handles both single-device and multi-device editing.

    Behavior depends on number of selected devices:
      - 0 selected: panel disabled.
      - 1 selected: live apply on every change.
      - 2+ selected: changes go to "pending" state, applied on Apply button.
    """

    name_changed = pyqtSignal(str, str)
    frequency_changed = pyqtSignal(str, int)
    sensitivity_changed = pyqtSignal(str, int)
    mode_changed = pyqtSignal(str, str)
    mute_changed = pyqtSignal(str, bool)
    eq_changed = pyqtSignal(str, bool, list)
    rf_power_changed = pyqtSignal(str, str)
    panel_lock_changed = pyqtSignal(str, bool)

    identify_selected = pyqtSignal(list)
    reset_selected = pyqtSignal(list)
    apply_pending = pyqtSignal(list, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices_by_ip: dict[str, IEMDevice] = {}
        self._selected_ips: list[str] = []
        self._suppress_signals = False
        self._pending: dict = {}
        self._eq_user_dragging = [False] * 5

        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)

        # --- Header ---
        header = QHBoxLayout()
        self._title = QLabel("No selection")
        self._title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(self._title)
        header.addStretch()
        self._select_all_btn = QPushButton("Select All")
        self._clear_btn = QPushButton("Clear")
        header.addWidget(self._select_all_btn)
        header.addWidget(self._clear_btn)
        root.addLayout(header)

        # --- Name + Frequency (single-device only) ---
        unique_row = QHBoxLayout()
        unique_row.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setMaximumWidth(140)
        self._name_apply = QPushButton("Set")
        self._name_apply.setMaximumWidth(40)
        unique_row.addWidget(self._name_edit)
        unique_row.addWidget(self._name_apply)
        unique_row.addSpacing(15)
        unique_row.addWidget(QLabel("Freq (MHz):"))
        self._freq_edit = QLineEdit()
        self._freq_edit.setMaximumWidth(110)
        self._freq_apply = QPushButton("Set")
        self._freq_apply.setMaximumWidth(40)
        unique_row.addWidget(self._freq_edit)
        unique_row.addWidget(self._freq_apply)
        unique_row.addStretch()
        root.addLayout(unique_row)

        # --- Common controls row ---
        common_row = QHBoxLayout()
        common_row.addWidget(QLabel("Sens:"))
        self._sens_combo = QComboBox()
        for v in IEMDevice.SENSITIVITY_VALUES:
            self._sens_combo.addItem(f"{v} dB", v)
        common_row.addWidget(self._sens_combo)

        common_row.addSpacing(10)
        common_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Stereo", "stereo")
        self._mode_combo.addItem("Mono", "mono")
        common_row.addWidget(self._mode_combo)

        common_row.addSpacing(10)
        common_row.addWidget(QLabel("RF Power:"))
        self._rf_combo = QComboBox()
        for v in RF_LEVELS:
            self._rf_combo.addItem(v, v)
        common_row.addWidget(self._rf_combo)

        common_row.addSpacing(10)
        self._lock_check = QCheckBox("Panel Lock")
        common_row.addWidget(self._lock_check)

        common_row.addSpacing(10)
        self._mute_check = QCheckBox("Mute")
        common_row.addWidget(self._mute_check)

        common_row.addStretch()
        root.addLayout(common_row)

        # --- EQ ---
        eq_group = QGroupBox("Equalizer")
        eq_outer = QHBoxLayout(eq_group)
        self._eq_enabled = QCheckBox("Enabled")
        eq_outer.addWidget(self._eq_enabled)
        self._eq_sliders: list[QSlider] = []
        self._eq_labels: list[QLabel] = []
        for i, band_name in enumerate(EQ_BANDS):
            band_layout = QVBoxLayout()
            label = QLabel("0")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setMinimum(-5)
            slider.setMaximum(5)
            slider.setValue(0)
            slider.setTickInterval(1)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.setMinimumHeight(120)
            slider.setFixedWidth(40)
            slider.sliderPressed.connect(lambda b=i: self._set_eq_drag(b, True))
            slider.sliderReleased.connect(lambda b=i: self._set_eq_drag(b, False))
            slider.valueChanged.connect(self._on_eq_changed)
            name_label = QLabel(band_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            band_layout.addWidget(label)
            band_layout.addWidget(slider)
            band_layout.addWidget(name_label)
            eq_outer.addLayout(band_layout)
            self._eq_sliders.append(slider)
            self._eq_labels.append(label)
        root.addWidget(eq_group)

        # --- Audio levels (single-device only) ---
        levels_row = QHBoxLayout()
        levels_row.addWidget(QLabel("Audio:"))
        levels_row.addWidget(QLabel("L"))
        self._level_l = QProgressBar()
        self._level_l.setMaximum(255)
        self._level_l.setTextVisible(False)
        levels_row.addWidget(self._level_l)
        levels_row.addWidget(QLabel("R"))
        self._level_r = QProgressBar()
        self._level_r.setMaximum(255)
        self._level_r.setTextVisible(False)
        levels_row.addWidget(self._level_r)
        root.addLayout(levels_row)

        # --- Action buttons ---
        actions_row = QHBoxLayout()
        self._identify_btn = QPushButton("💡 Identify Selected")
        self._reset_btn = QPushButton("↺ Reset Selected")
        self._apply_btn = QPushButton("Apply Changes")
        self._apply_btn.setEnabled(False)
        actions_row.addWidget(self._identify_btn)
        actions_row.addWidget(self._reset_btn)
        actions_row.addStretch()
        actions_row.addWidget(self._apply_btn)
        root.addLayout(actions_row)

        # Visual divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(div)

        # --- Global block ---
        global_row = QHBoxLayout()
        global_row.addWidget(QLabel("Global:"))
        self._mute_all_btn = QPushButton("🔇 Mute ALL")
        self._unmute_all_btn = QPushButton("🔊 Unmute ALL")
        self._identify_all_btn = QPushButton("💡 Identify ALL")
        global_row.addWidget(self._mute_all_btn)
        global_row.addWidget(self._unmute_all_btn)
        global_row.addWidget(self._identify_all_btn)
        global_row.addStretch()
        root.addLayout(global_row)

        # --- Wire signals ---
        self._name_apply.clicked.connect(self._on_name_apply)
        self._name_edit.returnPressed.connect(self._on_name_apply)
        self._freq_apply.clicked.connect(self._on_freq_apply)
        self._freq_edit.returnPressed.connect(self._on_freq_apply)
        self._sens_combo.currentIndexChanged.connect(self._on_sens_changed)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._rf_combo.currentIndexChanged.connect(self._on_rf_changed)
        self._lock_check.stateChanged.connect(self._on_lock_changed)
        self._mute_check.stateChanged.connect(self._on_mute_changed)
        self._eq_enabled.stateChanged.connect(self._on_eq_enabled_changed)
        self._identify_btn.clicked.connect(self._on_identify_selected)
        self._reset_btn.clicked.connect(self._on_reset_selected)
        self._apply_btn.clicked.connect(self._on_apply_clicked)

        self._refresh_enabled_state()

    # --- Public API ---

    def set_devices(self, devices_by_ip: dict[str, IEMDevice]):
        self._devices_by_ip = devices_by_ip
        self._refresh_view()

    def refresh_if_selected(self, ip: str):
        """Re-populate panel inputs only if the changed device is selected."""
        if ip in self._selected_ips:
            self._refresh_view()

    def set_selection(self, ips: list[str]):
        self._selected_ips = list(ips)
        self._pending.clear()
        self._apply_btn.setEnabled(False)
        self._refresh_view()

    def update_levels(self, ip: str):
        if len(self._selected_ips) != 1 or self._selected_ips[0] != ip:
            return
        dev = self._devices_by_ip.get(ip)
        if dev:
            self._level_l.setValue(dev.audio_level_l)
            self._level_r.setValue(dev.audio_level_r)

    # --- Internal: refresh ---

    def _refresh_view(self):
        n = len(self._selected_ips)
        if n == 0:
            self._title.setText("No selection")
        elif n == 1:
            dev = self._devices_by_ip.get(self._selected_ips[0])
            label = (dev.name or dev.ip) if dev else self._selected_ips[0]
            self._title.setText(f"Editing: {label}")
        else:
            self._title.setText(f"Editing: {n} selected")

        self._suppress_signals = True
        self._populate_inputs()
        self._suppress_signals = False
        self._refresh_enabled_state()

    def _populate_inputs(self):
        n = len(self._selected_ips)
        if n == 1:
            dev = self._devices_by_ip.get(self._selected_ips[0])
            if not dev:
                return
            self._name_edit.setText(dev.name)
            self._freq_edit.setText(dev.frequency_mhz)
            self._set_combo_data(self._sens_combo, dev.sensitivity)
            self._set_combo_data(self._mode_combo, dev.mode)
            self._set_combo_data(self._rf_combo, dev.rf_power)
            self._lock_check.setChecked(dev.panel_locked)
            self._mute_check.setChecked(dev.mute)
            self._eq_enabled.setChecked(any(b != 0 for b in dev.eq))
            for i, val in enumerate(dev.eq):
                if not self._eq_user_dragging[i]:
                    self._eq_sliders[i].setValue(val)
                    self._eq_labels[i].setText(str(val))
            self._level_l.setValue(dev.audio_level_l)
            self._level_r.setValue(dev.audio_level_r)
        elif n >= 2:
            devs = [self._devices_by_ip[ip] for ip in self._selected_ips if ip in self._devices_by_ip]
            self._name_edit.setText("")
            self._freq_edit.setText("")
            self._populate_common_combo(self._sens_combo, [d.sensitivity for d in devs])
            self._populate_common_combo(self._mode_combo, [d.mode for d in devs])
            self._populate_common_combo(self._rf_combo, [d.rf_power for d in devs])
            self._populate_common_check(self._lock_check, [d.panel_locked for d in devs])
            self._populate_common_check(self._mute_check, [d.mute for d in devs])
            for i in range(5):
                vals = {d.eq[i] for d in devs}
                if len(vals) == 1:
                    val = vals.pop()
                    if not self._eq_user_dragging[i]:
                        self._eq_sliders[i].setValue(val)
                        self._eq_labels[i].setText(str(val))
                else:
                    self._eq_sliders[i].setValue(0)
                    self._eq_labels[i].setText("--")
            self._level_l.setValue(0)
            self._level_r.setValue(0)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _populate_common_combo(combo: QComboBox, values: list):
        unique = set(values)
        if len(unique) == 1:
            ControlPanel._set_combo_data(combo, unique.pop())
        else:
            combo.setCurrentIndex(-1)

    @staticmethod
    def _populate_common_check(check: QCheckBox, values: list[bool]):
        unique = set(values)
        if len(unique) == 1:
            check.setChecked(unique.pop())
        else:
            check.setChecked(False)

    def _refresh_enabled_state(self):
        n = len(self._selected_ips)
        single = (n == 1)
        any_sel = (n >= 1)

        self._name_edit.setEnabled(single)
        self._name_apply.setEnabled(single)
        self._freq_edit.setEnabled(single)
        self._freq_apply.setEnabled(single)

        for w in (self._sens_combo, self._mode_combo, self._rf_combo,
                  self._lock_check, self._mute_check, self._eq_enabled,
                  *self._eq_sliders):
            w.setEnabled(any_sel)

        self._level_l.setEnabled(single)
        self._level_r.setEnabled(single)

        self._identify_btn.setEnabled(any_sel)
        self._reset_btn.setEnabled(any_sel)

    # --- EQ drag tracking ---

    def _set_eq_drag(self, band_idx: int, dragging: bool):
        self._eq_user_dragging[band_idx] = dragging

    # --- Live or pending dispatch ---

    def _emit_or_pend(self, field: str, value, single_signal_emitter):
        if self._suppress_signals:
            return
        n = len(self._selected_ips)
        if n == 1:
            single_signal_emitter(self._selected_ips[0], value)
        elif n >= 2:
            self._pending[field] = value
            self._apply_btn.setEnabled(True)

    # --- Input handlers ---

    def _on_name_apply(self):
        if len(self._selected_ips) == 1:
            self.name_changed.emit(self._selected_ips[0], self._name_edit.text())

    def _on_freq_apply(self):
        if len(self._selected_ips) != 1:
            return
        text = self._freq_edit.text().replace(".", "").replace(",", "")
        try:
            freq = int(text)
            if 470000 <= freq <= 865000:
                self._freq_edit.setStyleSheet("")
                self.frequency_changed.emit(self._selected_ips[0], freq)
            else:
                self._freq_edit.setStyleSheet("background-color: #ffcccc;")
        except ValueError:
            self._freq_edit.setStyleSheet("background-color: #ffcccc;")

    def _on_sens_changed(self, _idx):
        value = self._sens_combo.currentData()
        if value is None:
            return
        self._emit_or_pend("sensitivity", value,
                           lambda ip, v: self.sensitivity_changed.emit(ip, v))

    def _on_mode_changed(self, _idx):
        value = self._mode_combo.currentData()
        if value is None:
            return
        self._emit_or_pend("mode", value,
                           lambda ip, v: self.mode_changed.emit(ip, v))

    def _on_rf_changed(self, _idx):
        value = self._rf_combo.currentData()
        if value is None:
            return
        self._emit_or_pend("rf_power", value,
                           lambda ip, v: self.rf_power_changed.emit(ip, v))

    def _on_lock_changed(self, _state):
        value = self._lock_check.isChecked()
        self._emit_or_pend("panel_locked", value,
                           lambda ip, v: self.panel_lock_changed.emit(ip, v))

    def _on_mute_changed(self, _state):
        value = self._mute_check.isChecked()
        self._emit_or_pend("mute", value,
                           lambda ip, v: self.mute_changed.emit(ip, v))

    def _on_eq_changed(self, _val):
        if self._suppress_signals:
            return
        bands = [s.value() for s in self._eq_sliders]
        for i, val in enumerate(bands):
            self._eq_labels[i].setText(str(val))
        enabled = self._eq_enabled.isChecked() or any(b != 0 for b in bands)
        n = len(self._selected_ips)
        if n == 1:
            self.eq_changed.emit(self._selected_ips[0], enabled, bands)
        elif n >= 2:
            self._pending["eq"] = (enabled, bands)
            self._apply_btn.setEnabled(True)

    def _on_eq_enabled_changed(self, _state):
        self._on_eq_changed(0)

    def _on_identify_selected(self):
        if self._selected_ips:
            self.identify_selected.emit(list(self._selected_ips))

    def _on_reset_selected(self):
        if self._selected_ips:
            self.reset_selected.emit(list(self._selected_ips))

    def _on_apply_clicked(self):
        if not self._pending or not self._selected_ips:
            return
        self.apply_pending.emit(list(self._selected_ips), dict(self._pending))
        self._pending.clear()
        self._apply_btn.setEnabled(False)

    # --- Header buttons exposed to main_window ---

    @property
    def select_all_btn(self) -> QPushButton:
        return self._select_all_btn

    @property
    def clear_btn(self) -> QPushButton:
        return self._clear_btn

    @property
    def mute_all_btn(self) -> QPushButton:
        return self._mute_all_btn

    @property
    def unmute_all_btn(self) -> QPushButton:
        return self._unmute_all_btn

    @property
    def identify_all_btn(self) -> QPushButton:
        return self._identify_all_btn
