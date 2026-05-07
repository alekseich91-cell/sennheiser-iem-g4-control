import pytest
from unittest.mock import MagicMock, patch
from device import IEMDevice
from manager import DeviceManager


@pytest.fixture
def manager():
    """Create DeviceManager with mocked socket (no real network)."""
    with patch("manager.QUdpSocket"):
        mgr = DeviceManager()
        mgr._socket = MagicMock()
        mgr._socket.writeDatagram = MagicMock(return_value=0)
        return mgr


def test_add_device(manager):
    manager._add_device("192.168.1.10")
    assert "192.168.1.10" in manager.devices
    assert manager.devices["192.168.1.10"].ip == "192.168.1.10"
    assert manager.devices["192.168.1.10"].online is True


def test_add_device_duplicate(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.10")
    assert len(manager.devices) == 1


def test_apply_update_name(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "Name", "value": "IEM-01"})
    assert manager.devices["192.168.1.10"].name == "IEM-01"


def test_apply_update_frequency(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "Frequency", "value": 514125})
    assert manager.devices["192.168.1.10"].frequency == 514125


def test_apply_update_sensitivity(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "Sensitivity", "value": -12})
    assert manager.devices["192.168.1.10"].sensitivity == -12


def test_apply_update_states_muted(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "States", "mute": True, "flags": 0})
    assert manager.devices["192.168.1.10"].mute is True


def test_apply_update_mode(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "Mode", "value": "mono"})
    assert manager.devices["192.168.1.10"].mode == "mono"


def test_apply_update_equalizer(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "Equalizer", "enabled": True, "bands": [1, -2, 3, 0, -1]})
    assert manager.devices["192.168.1.10"].eq == [1, -2, 3, 0, -1]


def test_apply_update_af_levels(manager):
    manager._add_device("192.168.1.10")
    manager._apply_update("192.168.1.10", {"type": "AF", "peak_l": 120, "peak_r": 100, "hold_l": 80, "hold_r": 70})
    assert manager.devices["192.168.1.10"].audio_level_l == 120
    assert manager.devices["192.168.1.10"].audio_level_r == 100


def test_mass_set_sensitivity(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager._add_device("192.168.1.12")
    manager.mass_set_sensitivity(["192.168.1.10", "192.168.1.12"], -24)
    assert manager._socket.writeDatagram.call_count == 2


def test_mass_set_mute(manager):
    manager._add_device("192.168.1.10")
    manager._add_device("192.168.1.11")
    manager.mass_set_mute(["192.168.1.10", "192.168.1.11"], True)
    assert manager._socket.writeDatagram.call_count == 2


def test_offline_detection(manager):
    manager._add_device("192.168.1.10")
    dev = manager.devices["192.168.1.10"]
    dev._missed_pushes = 2
    manager._check_missed_push("192.168.1.10")
    assert dev._missed_pushes == 3
    assert dev.online is False


def test_online_restored_on_data(manager):
    manager._add_device("192.168.1.10")
    dev = manager.devices["192.168.1.10"]
    dev.online = False
    dev._missed_pushes = 5
    manager._apply_update("192.168.1.10", {"type": "AF", "peak_l": 50, "peak_r": 40, "hold_l": 20, "hold_r": 10})
    assert dev.online is True
    assert dev._missed_pushes == 0


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
