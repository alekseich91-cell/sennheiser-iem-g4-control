# IEM G4 Control — UX & Feature Improvements

**Date:** 2026-05-07
**Status:** Draft for review
**Builds on:** `2026-04-02-iem-g4-control-design.md`

## Goal

Расширить и упростить управление набором баз Sennheiser IEM G4 для аудио-инженера, который работает с 5–12 устройствами в живом эфире. Унифицировать одиночное и массовое управление, добавить недостающие параметры базы, исправить нерабочий эквалайзер, дать удобные «emergency»-кнопки.

## Non-goals

- RF Scan / выгрузка спектра из базы — отдельная исследовательская задача, в этот апдейт не входит.
- Save/Load пресет всей системы — отложено.
- Управление приёмниками (бодипаками EK IEM) — мы общаемся только с базой SR.

## Scope

### Фичи

1. **Fix EQ bug** — слайдеры эквалайзера в одиночной панели не реагируют на клик/перетягивание.
2. **Identify** — мигание LED на базе:
   - кнопка в строке таблицы (мгновенно одна база);
   - `Identify Selected` (все отмеченные чекбоксом);
   - `Identify ALL` (все известные базы).
3. **Унифицированная панель управления** — одна панель заменяет существующие `DeviceDetailPanel` и `MassActionsPanel`. Поведение зависит от количества выбранных устройств.
4. **RF Power** (Lo / Std / Hi) — управление мощностью передатчика per-device и массово.
5. **Panel Lock** — блокировка кнопок на самой базе, per-device и массово.
6. **Reset Selected to Defaults** — сброс параметров (sens=-18, mode=stereo, EQ=0, RF=Std, lock=off, mute=off) у выбранных. Имя и частота не трогаются.
7. **Select All / Clear Selection** — кнопки для удобства быстрого выбора.
8. **Global block** — `Mute ALL` / `Unmute ALL` / `Identify ALL`. Действуют на все устройства в сети независимо от выделения.
9. **Сортировка таблицы** — клик по заголовку столбца, порядок сохраняется в `QSettings`.
10. **Цвета строк** — muted=серый фон, offline=красный текст, AF-peak за последние 200ms=жёлтый.
11. **Логи** — события приложения и UDP-трафик пишутся в файл; пользователь может выгрузить лог через меню `Help → Export Logs…` для отправки разработчику.

## Architecture

Расширяется существующая трёхслойная модель. Новых слоёв не появляется.

```
GUI (PyQt6)        — main_window.py, device_table.py, control_panel.py (NEW, заменяет detail+mass)
Device Manager     — manager.py (+ методы для Identify / RF / LockMode / mass-варианты)
Protocol Layer     — protocol.py (+ парсинг RF / LockMode / Identify)
```

### Изменения по файлам

- **`protocol.py`** — расширить `parse_response` под новые типы ответов: `RF`, `LockMode`, `Identify`. `build_command` без изменений.
- **`device.py`** — добавить поля `rf_power: str = "Std"` и `panel_locked: bool = False`.
- **`manager.py`**:
  - команды: `set_rf_power(ip, level)`, `set_panel_lock(ip, locked)`, `identify(ip)`;
  - mass-варианты: `mass_set_mode`, `mass_set_eq`, `mass_set_rf_power`, `mass_set_panel_lock`, `mass_identify`, `mass_reset`, `mute_all`, `unmute_all`, `identify_all`;
  - `_query_all_params` дополняется запросами `RF` и `LockMode`.
- **`ui/control_panel.py`** (NEW) — единая панель, заменяет `device_detail.py` и `mass_actions.py`.
- **`ui/device_table.py`** — сортировка, новые колонки (RF, Lock, Identify-кнопка), цвета строк.
- **`ui/main_window.py`** — переподключить сигналы к новой `ControlPanel`, удалить разводку detail/mass, добавить Global-блок.

### Удаляются

- `ui/device_detail.py` — функционал переезжает в `control_panel.py`.
- `ui/mass_actions.py` — функционал переезжает в `control_panel.py`.

## UI Design

### Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Toolbar: [Scan] [Interface ▾]                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Device Table                                                                │
│  ☐ | IP | Name | Freq | Sens | RF | 🔒 | Online | 💡                         │
│  ...                                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─ Editing: 3 selected of 8 ──── [☑ Select All] [☐ Clear] ──────────────┐  │
│ │ Name [─────] Set     Freq [───.───] Set                                │  │
│ │ Sens [-18 dB ▾]   Mode [Stereo ▾]   RF Power [Std ▾]  Panel [☐ Lock] │  │
│ │ Mute [☐]                                                               │  │
│ │ EQ  L[─] LM[─] M[─] MH[─] H[─]   [☐ enabled]                          │  │
│ │ Audio L ▮▮▮▮      Audio R ▮▮▮▮      (только когда выбрана 1 база)     │  │
│ │ [💡 Identify Selected] [↺ Reset Selected] [Apply Changes]              │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│ ┌─ Global ──────────────────────────────────────────────────────────────┐  │
│ │ [🔇 Mute ALL] [🔊 Unmute ALL] [💡 Identify ALL]                       │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Поведение единой панели

| Selected | Поведение |
|---|---|
| 0 | Все контролы выключены, панель серая. |
| 1 | Контролы показывают значения этой базы. Любое изменение **уходит сразу** (live apply). `Identify Selected` / `Reset Selected` действуют на эту одну. |
| 2+ | `Name` / `Freq` / `Audio L` / `Audio R` выключены (уникальные значения). Остальные показывают общее значение, если оно одинаково; иначе — placeholder (`--`). Изменение **не уходит сразу** — становится pending, активируется кнопка `[Apply Changes]`. `Identify Selected` / `Reset Selected` — мгновенные, без Apply. |

### Таблица

- `setSortingEnabled(True)` — клик по заголовку сортирует.
- Текущая колонка/направление сортировки сохраняются в `QSettings` под ключом `table/sortColumn`, `table/sortOrder`.
- Новые колонки: `RF` (текст: Lo/Std/Hi), `🔒` (icon-only, ридонли), `💡` (per-row кнопка Identify).
- Цвета: `setBackground(QColor("#cccccc"))` для muted, `setForeground(QColor("#cc0000"))` для offline. AF-peak — `QTimer` 200ms на жёлтый фон, после возврат.

### Global-блок

Всегда активен независимо от выделения. Размещён под основной панелью с визуальным разделителем.

## Protocol Layer

### Существующие команды (не меняются)

`Push`, `Mute`, `Name`, `Frequency`, `Sensitivity`, `Mode`, `Equalizer`.

### Новые команды (стартовые гипотезы — валидируются при реализации на железе)

| Команда | Отправка | Ожидаемый ответ |
|---|---|---|
| Identify | `Identify 1\r` | `Identify 1` или ничего (no-op response) |
| Set RF Power | `RF Lo\r` / `RF Std\r` / `RF Hi\r` | `RF Std` |
| Get RF | `RF\r` | `RF Std` |
| Set Lock | `LockMode 1\r` / `LockMode 0\r` | `LockMode 1` |
| Get Lock | `LockMode\r` | `LockMode 0` |

**Валидация:** на первом этапе реализации — отправляем команды на одно реальное устройство, логируем UDP-трафик, корректируем синтаксис под ответ железа. Если команда `Identify` не поддерживается прошивкой — fallback: имитация миганием поля `Name` (`Name *IDENT*` → `Name <original>` × 3 раза за 2 секунды). Аудио не трогаем ни при каких обстоятельствах.

### Расширение `parse_response`

Добавить кейсы:
- `keyword == "RF"` → `{"type": "RF", "value": parts[1]}` (строка `Lo`/`Std`/`Hi`)
- `keyword == "LockMode"` → `{"type": "LockMode", "value": parts[1] == "1"}`
- `keyword == "Identify"` → `{"type": "Identify"}` (просто ack)

## EQ Bug Fix

Две причины фиксим профилактически (точная диагностика — при первом запуске с реальной базой):

1. **Высота вертикальных слайдеров.** В существующей `DeviceDetailPanel` `QSlider(Vertical)` лежит в `QHBoxLayout` без `setMinimumHeight`. Слайдер сжимается, перетянуть невозможно.
   → В `ControlPanel.__init__` для каждого EQ-слайдера: `slider.setMinimumHeight(120)`, `slider.setFixedWidth(40)`.

2. **Перезапись от Push-подписки.** Каждые 500ms прилетает `Equalizer ...` с текущими бандами и пере-устанавливает слайдер пока юзер тащит.
   → В `ControlPanel`: подключить `slider.sliderPressed` → флаг `self._user_editing_eq[band] = True`, `slider.sliderReleased` → флаг сбрасывается. Метод обновления состояния (`update_from_device`) пропускает банды с активным флагом.

После реализации — если баг не уйдёт, снимаем UDP-логи (уже выводятся через `print` в `manager._on_data_ready`) и точечно дорабатываем.

## Data Model Changes

```python
@dataclass
class IEMDevice:
    # ...existing fields...
    rf_power: str = "Std"           # "Lo" | "Std" | "Hi"
    panel_locked: bool = False
```

`Reset to Defaults` означает:
```python
sensitivity = -18
mode = "stereo"
eq = [0, 0, 0, 0, 0]
rf_power = "Std"
panel_locked = False
mute = False
# name и frequency НЕ трогаем
```

## Logging

Текущий код использует `print()` — невидимо в собранном `.app` / `.exe`. Заменяем на `logging`:

- Новый модуль `app_log.py` (или функция в `main.py`) настраивает корневой logger:
  - `RotatingFileHandler` → файл в платформенной директории:
    - macOS: `~/Library/Logs/SennheiserIEMControl/app.log`
    - Windows: `%LOCALAPPDATA%\SennheiserIEMControl\Logs\app.log`
    - Linux: `~/.local/share/SennheiserIEMControl/app.log`
  - `maxBytes=5_000_000`, `backupCount=2` — итого до ~15 МБ.
  - Уровень `INFO` по умолчанию, `DEBUG` для UDP-трафика (можно включить через env-переменную или скрытую настройку).
- Все `print(...)` в `manager.py` заменяем на `log.info(...)` / `log.debug(...)`.
- Формат: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`.

### UI

Меню `Help → Export Logs…`:
- Открывает `QFileDialog.getSaveFileName` с дефолтным именем `iem-log-YYYYMMDD-HHMMSS.txt`.
- Конкатенирует текущий `app.log` + `app.log.1` + `app.log.2` (если есть) и пишет в выбранный путь.
- Статус-бар: `"Logs exported to <path>"`.

Меню `Help → Show Log Folder` — открывает директорию логов в Finder/Explorer (через `QDesktopServices.openUrl`).

## Manager — новые публичные методы

```python
def set_rf_power(self, ip: str, level: str): ...        # "Lo"|"Std"|"Hi"
def set_panel_lock(self, ip: str, locked: bool): ...
def identify(self, ip: str): ...

def mass_set_mode(self, ips: list[str], mode: str): ...
def mass_set_eq(self, ips: list[str], enabled: bool, bands: list[int]): ...
def mass_set_rf_power(self, ips: list[str], level: str): ...
def mass_set_panel_lock(self, ips: list[str], locked: bool): ...
def mass_identify(self, ips: list[str]): ...
def mass_reset(self, ips: list[str]): ...

def mute_all(self): ...                                  # все известные
def unmute_all(self): ...
def identify_all(self): ...
```

Все mass-методы — простой цикл по `ips` с вызовом одиночной команды (как уже сделано для `mass_set_sensitivity` / `mass_set_mute`).

## Testing

### `test_protocol.py`
Добавить кейсы парсинга `RF Lo`, `RF Std`, `RF Hi`, `LockMode 1`, `LockMode 0`, `Identify 1`.

### `test_manager.py`
Добавить тесты:
- `set_rf_power` отправляет корректный UDP пакет (через mock-сокет, как уже сделано).
- `set_panel_lock` отправляет `LockMode 1`/`LockMode 0`.
- `mass_*` методы вызывают одиночные на каждом IP.
- `identify_all` отправляет на все известные IP.
- `mute_all` / `unmute_all` отправляют корректное состояние всем.

### Manual / hardware
- Запуск `python main.py`, scan → одно устройство:
  - EQ-слайдеры тянутся, изменения слышны;
  - `Identify` мигает LED-ом базы;
  - смена RF Power отражается на дисплее базы;
  - Lock блокирует кнопки на базе.
- 3+ устройства: проверить что `2+ selected` режим pending+Apply работает, `Mute ALL` мутит всех, `Identify ALL` мигает на всех.

## Build Sequence

Порядок предложен по принципу «риск низкий → высокий, чтоб промежуточные коммиты были полезные сами по себе»:

1. **EQ fix** — изолированно, маленький коммит. Сразу облегчает работу.
2. **Protocol layer** — расширение `parse_response`, новые `build_command`-обёртки в manager, тесты. Без UI.
3. **Data model** — поля `rf_power`, `panel_locked` в `IEMDevice`, прокидка в `_apply_update`.
4. **ControlPanel** — новый файл, замена `DeviceDetailPanel` и `MassActionsPanel`. Подключение к main_window. Удаление старых файлов.
5. **Table improvements** — сортировка, новые колонки, per-row Identify, цвета строк, persist в QSettings.
6. **Global block** — `Mute ALL` / `Unmute ALL` / `Identify ALL` в main_window.
7. **Logging** — настройка `RotatingFileHandler`, замена `print` на `log`, меню `Help → Export Logs…` / `Show Log Folder`. Делается до hardware validation чтобы можно было собирать логи с реального железа.
8. **Hardware validation** — прогон на реальном железе. Корректировка синтаксиса протокольных команд если стартовая гипотеза не подтвердится. Реализация fallback для Identify если нужно.

Каждый шаг — отдельный коммит с проходящими тестами.

## Open Questions

- Точный синтаксис команд `Identify` / `RF` / `LockMode` для конкретной прошивки SR IEM G4 — валидируется на первом запуске.
- Поддерживает ли SR команду `Identify` вообще — если нет, активируем fallback (мигание именем).
