from device import IEMDevice


def test_create_device_with_ip():
    dev = IEMDevice(ip="192.168.1.10")
    assert dev.ip == "192.168.1.10"
    assert dev.name == ""
    assert dev.frequency == 0
    assert dev.sensitivity == -18
    assert dev.mute is False
    assert dev.mode == "stereo"
    assert dev.eq == [0, 0, 0, 0, 0]
    assert dev.audio_level_l == 0
    assert dev.audio_level_r == 0
    assert dev.online is False


def test_device_frequency_mhz():
    dev = IEMDevice(ip="192.168.1.10", frequency=514125)
    assert dev.frequency_mhz == "514.125"


def test_device_frequency_mhz_zero():
    dev = IEMDevice(ip="192.168.1.10")
    assert dev.frequency_mhz == "000.000"


def test_device_sensitivity_values():
    """Sensitivity ranges from 0 to -42 in steps of 3."""
    dev = IEMDevice(ip="10.0.0.1", sensitivity=0)
    assert dev.sensitivity == 0
    dev2 = IEMDevice(ip="10.0.0.1", sensitivity=-42)
    assert dev2.sensitivity == -42
