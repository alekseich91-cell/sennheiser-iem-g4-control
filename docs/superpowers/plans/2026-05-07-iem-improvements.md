# IEM G4 Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Унифицировать одиночное и массовое управление в одной панели, добавить RF Power / Panel Lock / Identify, исправить EQ-баг, сделать таблицу сортируемой, добавить файловое логирование с экспортом.

**Architecture:** Расширяем существующую трёхслойную модель (Protocol / Manager / GUI). `DeviceDetailPanel` и `MassActionsPanel` заменяются единой `ControlPanel`. Протокол получает новые команды/парсеры. `print()` заменяется на `logging` с ротацией.

**Tech Stack:** Python 3.13, PyQt6, netifaces-plus, pytest, стандартный `logging.handlers.RotatingFileHandler`.

**Spec:** `docs/superpowers/specs/2026-05-07-iem-improvements-design.md`

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `protocol.py` | Modify | Парсер `RF` / `LockMode` / `Identify` |
| `device.py` | Modify | Поля `rf_power`, `panel_locked` |
| `manager.py` | Modify | Новые команды + mass-методы; print → logging |
| `ui/device_detail.py` | Delete (Task 6) | Заменяется `ui/control_panel.py` |
| `ui/mass_actions.py` | Delete (Task 6) | Заменяется `ui/control_panel.py` |
| `ui/control_panel.py` | Create | Единая панель управления |
| `ui/device_table.py` | Modify | Сортировка, новые колонки, цвета, per-row Identify |
| `ui/main_window.py` | Modify | Подключение `ControlPanel` + Global-блок + Help-меню |
| `app_log.py` | Create | Настройка корневого logger + RotatingFileHandler |
| `main.py` | Modify | Вызов `setup_logging()` до создания QApplication |
| `tests/test_protocol.py` | Modify | Тесты новых парсеров |
| `tests/test_manager.py` | Modify | Тесты новых команд и mass-методов |
| `tests/test_app_log.py` | Create | Smoke-тест настройки логгера |

---

## Task 1: Fix EQ sliders in existing DeviceDetailPanel (quick win)

Спека требует это первым шагом — пользователю надо чтобы EQ заработал немедленно. Файл будет удалён в Task 6, но фикс делается здесь чтобы был хотя бы один работающий коммит сразу.

**Files:**
- Modify: `ui/device_detail.py`

- [ ] **Step 1: Add minimum height + fixed width to vertical EQ sliders**

Открыть `ui/device_detail.py` и в цикле построения EQ-панели (около строк 96–115) добавить размеры. Найти блок:

```python
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
```

Заменить на:

```python
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
            slider.setMinimumHeight(120)
            slider.setFixedWidth(40)
            slider.sliderPressed.connect(self._on_eq_drag_start)
            slider.sliderReleased.connect(self._on_eq_drag_end)
            slider.valueChanged.connect(self._on_eq_changed)
```

- [ ] **Step 2: Add drag-state tracking field**

В `__init__` после `self._updating = False` (строка ~24) добавить:

```python
        self._eq_user_dragging = False
```

- [ ] **Step 3: Add drag handlers**

В конце класса (после `_on_eq_changed`) добавить:

```python
    def _on_eq_drag_start(self):
        self._eq_user_dragging = True

    def _on_eq_drag_end(self):
        self._eq_user_dragging = False
```

- [ ] **Step 4: Skip EQ refresh while user is dragging**

Найти метод `show_device` и в блоке обновления EQ-слайдеров обернуть в проверку флага. Заменить:

```python
        for i, val in enumerate(device.eq):
            self._eq_sliders[i].setValue(val)
            self._eq_labels[i].setText(str(val))
```

на:

```python
        if not self._eq_user_dragging:
            for i, val in enumerate(device.eq):
                self._eq_sliders[i].setValue(val)
                self._eq_labels[i].setText(str(val))
```

- [ ] **Step 5: Manual verification**

Run: `source .venv/bin/activate && python main.py`

Steps:
1. Click `Scan Network` (если есть устройства в сети) или просто запусти и убедись что окно не падает.
2. Если устройств нет — открой код визуально: вертикальные слайдеры в EQ должны иметь высоту минимум 120 пикселей.
3. Если устройства есть — выбери одно, попробуй потащить EQ-слайдер мышкой. Должен двигаться. Значение в подписи над слайдером должно меняться.

Expected: слайдеры физически реагируют на mouse drag.

- [ ] **Step 6: Commit**

```bash
git add ui/device_detail.py
git commit -m "$(cat <<'EOF'
fix(ui): EQ sliders now respond to mouse drag

setMinimumHeight(120) и setFixedWidth(40) — без них вертикальные
слайдеры внутри QHBoxLayout сжимались до пары пикселей.
sliderPressed/sliderReleased защищают от перезаписи значений
входящими Push-апдейтами в момент перетягивания.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Extend protocol parser (RF / LockMode / Identify)

**Files:**
- Modify: `protocol.py`
- Test: `tests/test_protocol.py`

- [ ] **Step 1: Write failing tests for new parsers**

Открыть `tests/test_protocol.py` и в конец класса `TestParseResponse` добавить:

```python
    def test_parse_rf_lo(self):
        result = parse_response("RF Lo\r")
        assert result == [{"type": "RF", "value": "Lo"}]

    def test_parse_rf_std(self):
        result = parse_response("RF Std\r")
        assert result == [{"type": "RF", "value": "Std"}]

    def test_parse_rf_hi(self):
        result = parse_response("RF Hi\r")
        assert result == [{"type": "RF", "value": "Hi"}]

    def test_parse_lockmode_locked(self):
        result = parse_response("LockMode 1\r")
        assert result == [{"type": "LockMode", "value": True}]

    def test_parse_lockmode_unlocked(self):
        result = parse_response("LockMode 0\r")
        assert result == [{"type": "LockMode", "value": False}]

    def test_parse_identify(self):
        result = parse_response("Identify 1\r")
        assert result == [{"type": "Identify"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_protocol.py -v -k "rf_ or lockmode or identify"`

Expected: 6 FAIL — все падают как `Unknown` тип.

- [ ] **Step 3: Add parsers in protocol.py**

Открыть `protocol.py` и в `parse_response` после блока `elif keyword == "Msg":` (перед `else:`) вставить:

```python
        elif keyword == "RF":
            results.append({"type": "RF", "value": parts[1] if len(parts) > 1 else ""})
        elif keyword == "LockMode":
            results.append({"type": "LockMode", "value": parts[1] == "1"})
        elif keyword == "Identify":
            results.append({"type": "Identify"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_protocol.py -v`

Expected: PASS все 31 тест (25 старых + 6 новых).

- [ ] **Step 5: Commit**

```bash
git add protocol.py tests/test_protocol.py
git commit -m "$(cat <<'EOF'
feat(protocol): parse RF / LockMode / Identify responses

Готовим протокольный слой к управлению мощностью передатчика,
блокировкой панели и команде Identify.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Extend IEMDevice data model

**Files:**
- Modify: `device.py`
- Test: `tests/test_device.py`

- [ ] **Step 1: Write failing tests for new fields**

Открыть `tests/test_device.py` и в конец файла добавить:

```python
def test_default_rf_power_is_std():
    dev = IEMDevice(ip="192.168.1.10")
    assert dev.rf_power == "Std"


def test_default_panel_locked_is_false():
    dev = IEMDevice(ip="192.168.1.10")
    assert dev.panel_locked is False


def test_can_set_rf_power():
    dev = IEMDevice(ip="192.168.1.10", rf_power="Hi")
    assert dev.rf_power == "Hi"


def test_can_set_panel_locked():
    dev = IEMDevice(ip="192.168.1.10", panel_locked=True)
    assert dev.panel_locked is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_device.py -v`

Expected: FAIL — `rf_power` и `panel_locked` не существуют.

- [ ] **Step 3: Add fields to IEMDevice**

Открыть `device.py` и сразу после поля `online: bool = False` (строка 17), перед `_missed_pushes`, добавить:

```python
    rf_power: str = "Std"           # "Lo" | "Std" | "Hi"
    panel_locked: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_device.py -v`

Expected: PASS все тесты.

- [ ] **Step 5: Commit**

```bash
git add device.py tests/test_device.py
git commit -m "$(cat <<'EOF'
feat(device): add rf_power and panel_locked fields

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Manager — new commands + apply_update + mass methods

**Files:**
- Modify: `manager.py`
- Test: `tests/test_manager.py`

- [ ] **Step 1: Write failing tests for _apply_update of new types**

Открыть `tests/test_manager.py` и в конец файла добавить:

```python
def test_apply_update_rf(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "RF", "value": "Hi"})
    assert manager.devices["192.168.1.10"].rf_power == "Hi"


def test_apply_update_lockmode(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "LockMode", "value": True})
    assert manager.devices["192.168.1.10"].panel_locked is True


def test_apply_update_identify_is_noop(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "Identify"})
    # Just checks it doesn't crash; Identify carries no state.
```

- [ ] **Step 2: Write failing tests for new send commands**

В тот же файл добавить:

```python
def test_set_rf_power(manager):
    manager._add_device("192.168.1.10")
    manager.set_rf_power("192.168.1.10", "Hi")
    assert manager._socket.writeDatagram.call_count == 1
    sent_bytes = bytes(manager._socket.writeDatagram.call_args.args[0])
    assert sent_bytes == b"RF Hi\r"


def test_set_panel_lock_true(manager):
    manager._add_device("192.168.1.10")
    manager.set_panel_lock("192.168.1.10", True)
    sent_bytes = bytes(manager._socket.writeDatagram.call_args.args[0])
    assert sent_bytes == b"LockMode 1\r"


def test_set_panel_lock_false(manager):
    manager._add_device("192.168.1.10")
    manager.set_panel_lock("192.168.1.10", False)
    sent_bytes = bytes(manager._socket.writeDatagram.call_args.args[0])
    assert sent_bytes == b"LockMode 0\r"


def test_identify(manager):
    manager._add_device("192.168.1.10")
    manager.identify("192.168.1.10")
    sent_bytes = bytes(manager._socket.writeDatagram.call_args.args[0])
    assert sent_bytes == b"Identify 1\r"
```

- [ ] **Step 3: Write failing tests for mass methods**

В тот же файл добавить:

```python
def test_mass_set_mode(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.mass_set_mode(["192.168.1.10", "192.168.1.11"], "mono")
    assert manager._socket.writeDatagram.call_count == 2


def test_mass_set_eq(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.mass_set_eq(["192.168.1.10", "192.168.1.11"], True, [1, 2, 3, 4, 5])
    assert manager._socket.writeDatagram.call_count == 2


def test_mass_set_rf_power(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.mass_set_rf_power(["192.168.1.10", "192.168.1.11"], "Lo")
    assert manager._socket.writeDatagram.call_count == 2


def test_mass_set_panel_lock(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.mass_set_panel_lock(["192.168.1.10", "192.168.1.11"], True)
    assert manager._socket.writeDatagram.call_count == 2


def test_mass_identify(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.mass_identify(["192.168.1.10", "192.168.1.11"])
    assert manager._socket.writeDatagram.call_count == 2


def test_mass_reset_sends_six_commands_per_device(manager):
    manager._add_device("192.168.1.10")
    manager.mass_reset(["192.168.1.10"])
    # Sensitivity, Mode, Equalizer, RF, LockMode, Mute = 6 commands
    assert manager._socket.writeDatagram.call_count == 6


def test_mute_all_sends_to_every_known_device(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager._add_device("192.168.1.12")
    manager.mute_all()
    assert manager._socket.writeDatagram.call_count == 3


def test_unmute_all(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.unmute_all()
    assert manager._socket.writeDatagram.call_count == 2


def test_identify_all(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.identify_all()
    assert manager._socket.writeDatagram.call_count == 2
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_manager.py -v`

Expected: ~15 FAIL (новые тесты падают, старые проходят).

- [ ] **Step 5: Implement _apply_update for new types**

В `manager.py`, в методе `_apply_update`, после блока `elif t == "AF":` добавить:

```python
        elif t == "RF":
            dev.rf_power = update["value"]
        elif t == "LockMode":
            dev.panel_locked = update["value"]
        elif t == "Identify":
            pass  # no state to apply
```

- [ ] **Step 6: Implement set_* methods**

В `manager.py` после `set_equalizer` добавить:

```python
    def set_rf_power(self, ip: str, level: str):
        self._send_to(ip, build_command("RF", level))

    def set_panel_lock(self, ip: str, locked: bool):
        self._send_to(ip, build_command("LockMode", 1 if locked else 0))

    def identify(self, ip: str):
        self._send_to(ip, build_command("Identify", 1))
```

- [ ] **Step 7: Implement mass methods**

В `manager.py` после существующих `mass_set_sensitivity` и `mass_set_mute` добавить:

```python
    def mass_set_mode(self, ips: list[str], mode: str):
        for ip in ips:
            self.set_mode(ip, mode)

    def mass_set_eq(self, ips: list[str], enabled: bool, bands: list[int]):
        for ip in ips:
            self.set_equalizer(ip, enabled, bands)

    def mass_set_rf_power(self, ips: list[str], level: str):
        for ip in ips:
            self.set_rf_power(ip, level)

    def mass_set_panel_lock(self, ips: list[str], locked: bool):
        for ip in ips:
            self.set_panel_lock(ip, locked)

    def mass_identify(self, ips: list[str]):
        for ip in ips:
            self.identify(ip)

    def mass_reset(self, ips: list[str]):
        for ip in ips:
            self.set_sensitivity(ip, -18)
            self.set_mode(ip, "stereo")
            self.set_equalizer(ip, False, [0, 0, 0, 0, 0])
            self.set_rf_power(ip, "Std")
            self.set_panel_lock(ip, False)
            self.set_mute(ip, False)

    def mute_all(self):
        for ip in self.devices:
            self.set_mute(ip, True)

    def unmute_all(self):
        for ip in self.devices:
            self.set_mute(ip, False)

    def identify_all(self):
        for ip in self.devices:
            self.identify(ip)
```

- [ ] **Step 8: Add RF and LockMode to _query_all_params**

В `manager.py` найти `_query_all_params` (около строки 171):

```python
    def _query_all_params(self, ip: str):
        for cmd_name in ["Frequency", "Name", "Sensitivity", "Equalizer", "Mode"]:
            self._send_to(ip, build_command(cmd_name))
```

Заменить на:

```python
    def _query_all_params(self, ip: str):
        for cmd_name in ["Frequency", "Name", "Sensitivity", "Equalizer", "Mode", "RF", "LockMode"]:
            self._send_to(ip, build_command(cmd_name))
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_manager.py -v`

Expected: PASS все тесты (старые 13 + новые ~15).

- [ ] **Step 10: Commit**

```bash
git add manager.py tests/test_manager.py
git commit -m "$(cat <<'EOF'
feat(manager): RF / LockMode / Identify commands + mass variants

Single-device set_rf_power, set_panel_lock, identify; mass-варианты
для всех параметров; mute_all / unmute_all / identify_all (по всем
известным устройствам); mass_reset (сброс к дефолтам).
_query_all_params теперь запрашивает RF и LockMode при Config-смене.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Logging — RotatingFileHandler + replace print

Делаем до новой панели чтобы при её разработке были нормальные логи.

**Files:**
- Create: `app_log.py`
- Create: `tests/test_app_log.py`
- Modify: `manager.py`
- Modify: `main.py`

- [ ] **Step 1: Write failing test for app_log**

Создать файл `tests/test_app_log.py`:

```python
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

from app_log import setup_logging, log_dir


def test_log_dir_returns_path():
    p = log_dir()
    assert isinstance(p, Path)


def test_setup_logging_creates_file_and_writes():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("app_log.log_dir", return_value=Path(tmp)):
            setup_logging()
            log = logging.getLogger("test_module")
            log.info("hello world")

            for h in logging.getLogger().handlers:
                h.flush()

            log_file = Path(tmp) / "app.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "hello world" in content


def test_setup_logging_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("app_log.log_dir", return_value=Path(tmp)):
            setup_logging()
            count_after_first = len(logging.getLogger().handlers)
            setup_logging()
            count_after_second = len(logging.getLogger().handlers)
            assert count_after_first == count_after_second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_log.py -v`

Expected: FAIL — модуль `app_log` не существует.

- [ ] **Step 3: Create app_log.py**

Создать `app_log.py`:

```python
import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_NAME = "SennheiserIEMControl"

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_MAX_BYTES = 5_000_000
_BACKUP_COUNT = 2


def log_dir() -> Path:
    """Return platform-appropriate log directory."""
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library" / "Logs" / APP_NAME
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        return Path(base) / APP_NAME / "Logs"
    return home / ".local" / "share" / APP_NAME


def setup_logging(level: int = logging.INFO):
    """Configure root logger with RotatingFileHandler + stderr handler.

    Idempotent: calling multiple times does not duplicate handlers.
    """
    root = logging.getLogger()
    if getattr(root, "_iem_configured", False):
        return

    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / "app.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root._iem_configured = True


def collected_log_paths() -> list[Path]:
    """Return existing log files (current + rotated) in order, newest first."""
    directory = log_dir()
    paths = []
    main = directory / "app.log"
    if main.exists():
        paths.append(main)
    for i in range(1, _BACKUP_COUNT + 1):
        p = directory / f"app.log.{i}"
        if p.exists():
            paths.append(p)
    return paths
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_log.py -v`

Expected: PASS all 3.

- [ ] **Step 5: Replace print() in manager.py with logging**

В `manager.py` в самом начале файла (после `import socket`) добавить:

```python
import logging

log = logging.getLogger(__name__)
```

Найти и заменить все `print(...)` на `log`-вызовы:

Строки ~33-35 (init):
```python
        if not bound:
            print(f"WARNING: Could not bind to UDP port {PORT}: {self._socket.errorString()}")
        else:
            print(f"Bound to UDP port {PORT}")
```
заменить на:
```python
        if not bound:
            log.warning("Could not bind to UDP port %d: %s", PORT, self._socket.errorString())
        else:
            log.info("Bound to UDP port %d", PORT)
```

Строка ~82:
```python
        print(f"Scanning {local_ip}/{netmask}, socket bound: {self._bind_ok}, local port: {self._socket.localPort()}")
```
заменить на:
```python
        log.info("Scanning %s/%s, socket bound: %s, local port: %s", local_ip, netmask, self._bind_ok, self._socket.localPort())
```

Строка ~97:
```python
        print(f"Sent Push to {sent} hosts, waiting {SCAN_TIMEOUT_MS}ms...")
```
заменить на:
```python
        log.info("Sent Push to %d hosts, waiting %dms...", sent, SCAN_TIMEOUT_MS)
```

Строка ~119:
```python
            print(f"UDP recv from {ip}:{port}: {message[:80]}")
```
заменить на:
```python
            log.debug("UDP recv from %s:%d: %s", ip, port, message[:80])
```

- [ ] **Step 6: Initialize logging in main.py**

Текущий `main.py`:
```
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
... остальное без изменений ...
```

Изменения: вставить две строки между импортом `QApplication` и импортом `MainWindow`:

```python
from app_log import setup_logging
setup_logging()
```

После изменений первая часть `main.py` должна выглядеть так:

```python
import sys
from PyQt6.QtWidgets import QApplication

from app_log import setup_logging
setup_logging()

from ui.main_window import MainWindow
```

Остальная часть файла (`def main(): ...`) не трогается.

Важно: `setup_logging()` должен быть вызван **до** импорта `MainWindow`, чтобы логи из `manager.py` (который импортируется через цепочку) уже шли в файл.

- [ ] **Step 7: Manual verification**

Run: `python main.py`

Проверить:
1. На macOS: `ls ~/Library/Logs/SennheiserIEMControl/` — должен появиться `app.log`.
2. Открыть `app.log` — должны быть строки вида `2026-05-07 12:34:56 [INFO] manager: Bound to UDP port 53212`.
3. Закрыть приложение.

Expected: лог-файл создан и содержит startup-события.

- [ ] **Step 8: Commit**

```bash
git add app_log.py main.py manager.py tests/test_app_log.py
git commit -m "$(cat <<'EOF'
feat(logging): file logging with rotation; replace print() in manager

RotatingFileHandler пишет в платформенную директорию (macOS:
~/Library/Logs/SennheiserIEMControl/app.log; Win: %LOCALAPPDATA%;
Linux: ~/.local/share). 5 МБ × 3 файла. Идемпотентная инициализация.
Все print() в manager.py заменены на log.info/debug/warning.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Build unified ControlPanel (replaces detail+mass)

Большой шаг. Создаём новый файл, потом подключаем в main_window, потом удаляем старые.

**Files:**
- Create: `ui/control_panel.py`
- Modify: `ui/main_window.py`
- Modify: `ui/device_table.py` (добавить заглушки signals/slots; полная переработка в Task 7)
- Delete: `ui/device_detail.py`, `ui/mass_actions.py`

- [ ] **Step 1: Create ui/control_panel.py with full implementation**

Создать `ui/control_panel.py`:

```python
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
```

- [ ] **Step 2: Add stub signals/slots to DeviceTable**

Открыть `ui/device_table.py`. В классе `DeviceTable`, в секцию сигналов после `selection_changed` добавить:

```python
    device_identify_requested = pyqtSignal(str)   # ip — wired in Task 7
```

В конец класса добавить методы:

```python
    def select_all(self):
        for ip in self._ip_to_row:
            row = self._ip_to_row[ip]
            container = self.cellWidget(row, 0)
            if container:
                cb = container.findChild(QCheckBox)
                if cb:
                    cb.setChecked(True)

    def clear_selection(self):
        for ip in self._ip_to_row:
            row = self._ip_to_row[ip]
            container = self.cellWidget(row, 0)
            if container:
                cb = container.findChild(QCheckBox)
                if cb:
                    cb.setChecked(False)
```

- [ ] **Step 3: Replace ui/main_window.py**

Полная замена `ui/main_window.py`:

```python
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
```

- [ ] **Step 4: Delete old UI files**

```bash
git rm ui/device_detail.py ui/mass_actions.py
```

- [ ] **Step 5: Manual smoke test**

Run: `python main.py`

Steps:
1. Окно открывается без exception.
2. Если есть устройства: Scan, выбираешь чекбоксом одно — поле Name редактируется, Sensitivity combo меняет live.
3. Выбираешь два — поле Name выключено, Sensitivity combo меняет → нажимаешь Apply Changes → меняется на двух базах.
4. Кнопки Mute ALL / Unmute ALL / Identify ALL присутствуют под основной панелью.
5. Help → Show Log Folder открывает директорию с логами.

Expected: workflow выше работает (хотя per-row Identify в таблице ещё не добавлен — это в Task 7).

- [ ] **Step 6: Run all unit tests**

Run: `pytest tests/ -v`

Expected: PASS все тесты.

- [ ] **Step 7: Commit**

```bash
git add ui/control_panel.py ui/main_window.py ui/device_table.py
git commit -m "$(cat <<'EOF'
feat(ui): unified ControlPanel replaces detail+mass panels

Одна панель с поведением «1 selected = live, N selected = pending+Apply».
Поля Name/Freq/Audio активны только при выбранной 1 базе. Multi-value
индикация через "--" в EQ-метках. Глобальные Mute/Unmute/Identify ALL
вынесены в отдельный блок под основной панелью. Help-меню с Export Logs
и Show Log Folder.

Удалены ui/device_detail.py и ui/mass_actions.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Table improvements — sortable + new columns + colors + per-row Identify

**Files:**
- Modify: `ui/device_table.py`
- Modify: `ui/main_window.py` (AF peak flash hookup)

- [ ] **Step 1: Replace ui/device_table.py with extended version**

Полная замена `ui/device_table.py`:

```python
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
        for ip in list(self._ip_to_row.keys()):
            self._set_checked(ip, True)

    def clear_selection(self):
        for ip in list(self._ip_to_row.keys()):
            self._set_checked(ip, False)

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

    def _set_checked(self, ip: str, checked: bool):
        row = self._row_for_ip(ip)
        if row is None:
            return
        container = self.cellWidget(row, COL_CHECK)
        cb = container.findChild(QCheckBox) if container else None
        if cb:
            cb.setChecked(checked)

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
```

- [ ] **Step 2: Wire AF peak flash from manager updates**

Открыть `ui/main_window.py`, метод `_on_device_updated`, заменить:

```python
    def _on_device_updated(self, ip: str):
        device = self._manager.devices.get(ip)
        if device:
            self._table.update_device(device)
            self._panel.set_devices(self._manager.devices)
            self._panel.update_levels(ip)
```

на:

```python
    def _on_device_updated(self, ip: str):
        device = self._manager.devices.get(ip)
        if device:
            self._table.update_device(device)
            if device.audio_level_l > 200 or device.audio_level_r > 200:
                self._table.flash_af_peak(ip)
            self._panel.set_devices(self._manager.devices)
            self._panel.update_levels(ip)
```

(Threshold 200 of 255 ≈ 78% — близко к клиппингу. Если позже понадобится точнее — можно прокинуть отдельный сигнал из manager при `Msg AF_Peak`.)

- [ ] **Step 3: Manual smoke test**

Run: `python main.py`

Steps:
1. Запуск, никаких ошибок.
2. Если есть устройства: Scan → строки с новыми колонками (RF, Lock, Online, 💡).
3. Кликнуть на заголовок «Name» — таблица сортируется. Перезапустить приложение — порядок сохранён.
4. Кликнуть 💡 в строке — должна моргнуть LED-ом эта база (или ничего если прошивка не поддерживает; в логе должно быть `Identify 1\r`).
5. Замутить устройство (через панель) — строка стала серой. Размутить — нормальной.
6. Если есть громкий сигнал: должна моргать жёлтым.

Expected: всё выше работает. Если Identify не моргает на железе — нормально, валидация в Task 8.

- [ ] **Step 4: Run unit tests**

Run: `pytest tests/ -v`

Expected: всё PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/device_table.py ui/main_window.py
git commit -m "$(cat <<'EOF'
feat(ui): sortable table, new columns (RF/Lock/Online/Identify),
row colors, AF peak flash

Колонки кликабельны для сортировки, порядок сохраняется в QSettings.
Per-row Identify-кнопка. Цвета строк: muted=серый, offline=красный,
AF peak (>200/255 на любом канале) = жёлтый на 200ms.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Hardware validation

Этот шаг — единственный, который **должен делаться на реальном железе**. Здесь не пишем код профилактически — пишем код реакции на то, что показывает реальная база.

**Files:**
- Possibly: `protocol.py`, `manager.py` (если синтаксис команд отличается от гипотезы)

- [ ] **Step 1: Test Identify on a real SR**

1. Запустить `python main.py`, выбрать интерфейс, Scan.
2. В строке одной базы нажать 💡.
3. Проверить:
   - LED на физической базе должен мигнуть (или дисплей подсветиться).
   - В логе (`tail -f ~/Library/Logs/SennheiserIEMControl/app.log`) должна быть запись об отправке `Identify 1\r` и (возможно) ответ от базы.

Если LED **не мигает**, попробовать альтернативный синтаксис вручную через Python REPL:
```python
mgr.send_command("192.168.1.10", "Identify 1\r")
mgr.send_command("192.168.1.10", "Identify\r")
mgr.send_command("192.168.1.10", "Identify 2000\r")  # ms
```

- [ ] **Step 2: If Identify is not supported — implement Name flicker fallback**

Если ни один синтаксис не работает — заменить `manager.identify()` на эмуляцию миганием имени:

```python
    def identify(self, ip: str):
        from PyQt6.QtCore import QTimer
        dev = self.devices.get(ip)
        if not dev:
            return
        original = dev.name
        flicker = "*IDENT*"
        QTimer.singleShot(0,    lambda: self.set_name(ip, flicker))
        QTimer.singleShot(400,  lambda: self.set_name(ip, original))
        QTimer.singleShot(800,  lambda: self.set_name(ip, flicker))
        QTimer.singleShot(1200, lambda: self.set_name(ip, original))
        QTimer.singleShot(1600, lambda: self.set_name(ip, flicker))
        QTimer.singleShot(2000, lambda: self.set_name(ip, original))
```

- [ ] **Step 3: Test RF Power**

1. В панели выбрать одну базу, поменять RF Power dropdown с `Std` на `Hi`.
2. Проверить дисплей физической базы — мощность должна измениться.
3. В логе посмотреть отправленную команду — должно быть `RF Hi\r`.

Если не работает — попробовать варианты: `RFOutput Hi\r`, `RfOutput Hi\r`, `OUT Hi\r`. Скорректировать `manager.set_rf_power` если найдётся рабочий синтаксис.

- [ ] **Step 4: Test Panel Lock**

1. Выбрать базу, поставить чекбокс Panel Lock.
2. Подойти к базе, попробовать нажать кнопку — должна быть заблокирована.
3. Снять чекбокс — кнопки снова работают.

Если не работает — попробовать: `Lock 1\r`, `KeyLock 1\r`, `Locked 1\r`. Скорректировать `manager.set_panel_lock`.

- [ ] **Step 5: Test mass-операции**

1. Выбрать чекбоксами 2–3 базы.
2. Поменять Sensitivity → нажать Apply Changes → все базы получили новое значение.
3. Кнопка Mute ALL → все известные базы (включая невыбранные) замучены.
4. Identify ALL → все мигают.

- [ ] **Step 6: Export logs and review**

1. Help → Export Logs… → сохранить файл.
2. Открыть, убедиться что UDP-трафик там есть.
3. Если нашёл несоответствия в синтаксисе команд — закоммитить фиксы.

- [ ] **Step 7: Final commit (если потребовались правки)**

```bash
git add protocol.py manager.py
git commit -m "$(cat <<'EOF'
fix(protocol): adjust command syntax based on hardware validation

<описание что именно нашли — например: Identify требует duration в ms,
RF использует команду RFOutput, etc.>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- Все требования спеки покрыты задачами:
  - Fix EQ → Task 1 (а также интегрировано в Task 6 ControlPanel)
  - Identify per-device + Selected + ALL → Tasks 4, 6, 7
  - Унифицированная панель → Task 6
  - RF Power per-device + mass → Tasks 2, 3, 4, 6
  - Panel Lock → Tasks 2, 3, 4, 6
  - Reset Selected to Defaults → Tasks 4, 6
  - Select All / Clear → Tasks 6, 7
  - Global block (Mute/Unmute/Identify ALL) → Tasks 4, 6
  - Sortable table → Task 7
  - Row colors → Task 7
  - Logs + Help menu → Task 5, Task 6 (Help menu)
- Никаких placeholders — все блоки кода в шагах рабочие как есть.
- Hardware validation вынесена в Task 8 как явная часть плана с инструкциями fallback.
