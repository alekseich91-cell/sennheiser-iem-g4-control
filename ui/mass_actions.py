from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import pyqtSignal

from device import IEMDevice


class MassActionsPanel(QWidget):
    sensitivity_apply = pyqtSignal(int)     # sensitivity value
    mute_all = pyqtSignal()
    unmute_all = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self._label = QLabel("Selected: 0")
        layout.addWidget(self._label)

        layout.addSpacing(20)

        layout.addWidget(QLabel("Sensitivity:"))
        self._sens_combo = QComboBox()
        for val in IEMDevice.SENSITIVITY_VALUES:
            self._sens_combo.addItem(f"{val} dB", val)
        self._sens_combo.setCurrentIndex(6)  # -18 dB default
        layout.addWidget(self._sens_combo)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(self._apply_btn)

        layout.addSpacing(20)

        self._mute_btn = QPushButton("Mute All")
        self._mute_btn.clicked.connect(self.mute_all.emit)
        layout.addWidget(self._mute_btn)

        self._unmute_btn = QPushButton("Unmute All")
        self._unmute_btn.clicked.connect(self.unmute_all.emit)
        layout.addWidget(self._unmute_btn)

        layout.addStretch()
        self.set_enabled(False)

    def update_selection_count(self, count: int):
        self._label.setText(f"Selected: {count}")
        self.set_enabled(count > 0)

    def set_enabled(self, enabled: bool):
        self._apply_btn.setEnabled(enabled)
        self._mute_btn.setEnabled(enabled)
        self._unmute_btn.setEnabled(enabled)
        self._sens_combo.setEnabled(enabled)

    def _on_apply(self):
        value = self._sens_combo.currentData()
        self.sensitivity_apply.emit(value)
