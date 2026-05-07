from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QSlider, QComboBox, QPushButton, QProgressBar, QGroupBox,
)
from PyQt6.QtCore import pyqtSignal, Qt

from device import IEMDevice


EQ_BANDS = ["Low", "Low Mid", "Mid", "Mid High", "High"]


class DeviceDetailPanel(QWidget):
    name_changed = pyqtSignal(str, str)           # ip, name
    frequency_changed = pyqtSignal(str, int)      # ip, freq_khz
    sensitivity_changed = pyqtSignal(str, int)    # ip, value
    mode_changed = pyqtSignal(str, str)           # ip, "mono"/"stereo"
    mute_changed = pyqtSignal(str, bool)          # ip, mute
    eq_changed = pyqtSignal(str, bool, list)      # ip, enabled, [5 bands]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_ip: str | None = None
        self._updating = False  # Guard against signal loops

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self._title = QLabel("No device selected")
        self._title.setStyleSheet("font-weight: bold; font-size: 14px;")
        main_layout.addWidget(self._title)

        # --- Top row: name, frequency, mode, mute ---
        top = QHBoxLayout()

        top.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setMaximumWidth(120)
        self._name_edit.returnPressed.connect(self._on_name_changed)
        top.addWidget(self._name_edit)
        self._name_apply = QPushButton("Set")
        self._name_apply.setMaximumWidth(40)
        self._name_apply.clicked.connect(self._on_name_changed)
        top.addWidget(self._name_apply)

        top.addSpacing(10)
        top.addWidget(QLabel("Freq (MHz):"))
        self._freq_edit = QLineEdit()
        self._freq_edit.setMaximumWidth(100)
        self._freq_edit.returnPressed.connect(self._on_freq_changed)
        top.addWidget(self._freq_edit)
        self._freq_apply = QPushButton("Set")
        self._freq_apply.setMaximumWidth(40)
        self._freq_apply.clicked.connect(self._on_freq_changed)
        top.addWidget(self._freq_apply)

        top.addSpacing(10)
        top.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Stereo", "stereo")
        self._mode_combo.addItem("Mono", "mono")
        top.addWidget(self._mode_combo)
        self._mode_apply = QPushButton("Set")
        self._mode_apply.setMaximumWidth(40)
        self._mode_apply.clicked.connect(self._on_mode_changed)
        top.addWidget(self._mode_apply)

        top.addSpacing(10)
        self._mute_btn = QPushButton("Mute: Off")
        self._mute_btn.setCheckable(True)
        self._mute_btn.clicked.connect(self._on_mute_clicked)
        top.addWidget(self._mute_btn)

        top.addStretch()
        main_layout.addLayout(top)

        # --- Sensitivity ---
        sens_layout = QHBoxLayout()
        sens_layout.addWidget(QLabel("Sensitivity:"))
        self._sens_slider = QSlider(Qt.Orientation.Horizontal)
        self._sens_slider.setMinimum(0)
        self._sens_slider.setMaximum(14)  # 15 steps: index 0=0dB, 14=-42dB
        self._sens_slider.setTickInterval(1)
        self._sens_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._sens_slider.valueChanged.connect(self._on_sens_changed)
        sens_layout.addWidget(self._sens_slider)
        self._sens_label = QLabel("-18 dB")
        self._sens_label.setMinimumWidth(50)
        sens_layout.addWidget(self._sens_label)
        main_layout.addLayout(sens_layout)

        # --- EQ ---
        eq_group = QGroupBox("Equalizer")
        eq_layout = QHBoxLayout(eq_group)
        self._eq_sliders: list[QSlider] = []
        self._eq_labels: list[QLabel] = []
        for band_name in EQ_BANDS:
            band_layout = QVBoxLayout()
            label = QLabel("0")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setMinimum(-5)
            slider.setMaximum(5)
            slider.setValue(0)
            slider.setTickInterval(1)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.valueChanged.connect(self._on_eq_changed)
            name_label = QLabel(band_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            band_layout.addWidget(label)
            band_layout.addWidget(slider)
            band_layout.addWidget(name_label)
            eq_layout.addLayout(band_layout)
            self._eq_sliders.append(slider)
            self._eq_labels.append(label)
        main_layout.addWidget(eq_group)

        # --- Audio levels ---
        levels_layout = QHBoxLayout()
        levels_layout.addWidget(QLabel("Audio:"))
        levels_layout.addWidget(QLabel("L"))
        self._level_l = QProgressBar()
        self._level_l.setMaximum(255)
        self._level_l.setTextVisible(False)
        levels_layout.addWidget(self._level_l)
        levels_layout.addWidget(QLabel("R"))
        self._level_r = QProgressBar()
        self._level_r.setMaximum(255)
        self._level_r.setTextVisible(False)
        levels_layout.addWidget(self._level_r)
        main_layout.addLayout(levels_layout)

        self.setVisible(False)

    def show_device(self, device: IEMDevice):
        self._updating = True
        self._current_ip = device.ip
        self._title.setText(f"Device: {device.name or device.ip}")
        self._name_edit.setText(device.name)
        self._freq_edit.setText(device.frequency_mhz)

        idx = self._mode_combo.findData(device.mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)

        self._mute_btn.setChecked(device.mute)
        self._mute_btn.setText(f"Mute: {'On' if device.mute else 'Off'}")

        sens_idx = abs(device.sensitivity) // 3
        self._sens_slider.setValue(sens_idx)
        self._sens_label.setText(f"{device.sensitivity} dB")

        for i, val in enumerate(device.eq):
            self._eq_sliders[i].setValue(val)
            self._eq_labels[i].setText(str(val))

        self._level_l.setValue(device.audio_level_l)
        self._level_r.setValue(device.audio_level_r)

        self._updating = False
        self.setVisible(True)

    def update_levels(self, device: IEMDevice):
        if self._current_ip != device.ip:
            return
        self._level_l.setValue(device.audio_level_l)
        self._level_r.setValue(device.audio_level_r)

        self._updating = True
        self._mute_btn.setChecked(device.mute)
        self._mute_btn.setText(f"Mute: {'On' if device.mute else 'Off'}")
        self._updating = False

    def _on_name_changed(self):
        if self._current_ip and not self._updating:
            self.name_changed.emit(self._current_ip, self._name_edit.text())

    def _on_freq_changed(self):
        if self._current_ip and not self._updating:
            text = self._freq_edit.text().replace(".", "").replace(",", "")
            try:
                freq = int(text)
                if 470000 <= freq <= 865000:
                    self._freq_edit.setStyleSheet("")
                    self.frequency_changed.emit(self._current_ip, freq)
                else:
                    self._freq_edit.setStyleSheet("background-color: #ffcccc;")
            except ValueError:
                self._freq_edit.setStyleSheet("background-color: #ffcccc;")

    def _on_sens_changed(self, index):
        if self._current_ip and not self._updating:
            value = -(index * 3)
            self._sens_label.setText(f"{value} dB")
            self.sensitivity_changed.emit(self._current_ip, value)

    def _on_mode_changed(self):
        if self._current_ip and not self._updating:
            mode = self._mode_combo.currentData()
            self.mode_changed.emit(self._current_ip, mode)

    def _on_mute_clicked(self):
        if self._current_ip and not self._updating:
            mute = self._mute_btn.isChecked()
            self._mute_btn.setText(f"Mute: {'On' if mute else 'Off'}")
            self.mute_changed.emit(self._current_ip, mute)

    def _on_eq_changed(self):
        if self._current_ip and not self._updating:
            bands = [s.value() for s in self._eq_sliders]
            for i, val in enumerate(bands):
                self._eq_labels[i].setText(str(val))
            enabled = any(b != 0 for b in bands)
            self.eq_changed.emit(self._current_ip, enabled, bands)
