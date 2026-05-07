from protocol import build_command, parse_response


class TestBuildCommand:
    def test_push_subscribe(self):
        assert build_command("Push", 60, 1000, 3) == "Push 60 1000 3\r"

    def test_mute_on(self):
        assert build_command("Mute", 1) == "Mute 1\r"

    def test_mute_off(self):
        assert build_command("Mute", 0) == "Mute 0\r"

    def test_frequency(self):
        assert build_command("Frequency", 514125) == "Frequency 514125\r"

    def test_sensitivity(self):
        assert build_command("Sensitivity", -18) == "Sensitivity -18\r"

    def test_mode_stereo(self):
        assert build_command("Mode", 1) == "Mode 1\r"

    def test_mode_mono(self):
        assert build_command("Mode", 0) == "Mode 0\r"

    def test_name(self):
        assert build_command("Name", "IEM-01") == "Name IEM-01\r"

    def test_equalizer(self):
        assert build_command("Equalizer", "#1", 0, -2, 3, 0, 1) == "Equalizer #1 0 -2 3 0 1\r"

    def test_query_no_args(self):
        assert build_command("Frequency") == "Frequency\r"


class TestParseResponse:
    def test_parse_name(self):
        result = parse_response("Name IEM-01\r")
        assert result == [{"type": "Name", "value": "IEM-01"}]

    def test_parse_frequency(self):
        result = parse_response("Frequency 514125\r")
        assert result == [{"type": "Frequency", "value": 514125}]

    def test_parse_sensitivity(self):
        result = parse_response("Sensitivity -18\r")
        assert result == [{"type": "Sensitivity", "value": -18}]

    def test_parse_mode_stereo(self):
        result = parse_response("Mode 1\r")
        assert result == [{"type": "Mode", "value": "stereo"}]

    def test_parse_mode_mono(self):
        result = parse_response("Mode 0\r")
        assert result == [{"type": "Mode", "value": "mono"}]

    def test_parse_states(self):
        result = parse_response("States 1 0\r")
        assert result == [{"type": "States", "mute": True, "flags": 0}]

    def test_parse_states_unmuted(self):
        result = parse_response("States 0 0\r")
        assert result == [{"type": "States", "mute": False, "flags": 0}]

    def test_parse_af_levels(self):
        result = parse_response("AF 120 115 80 75\r")
        assert result == [{"type": "AF", "peak_l": 120, "peak_r": 115, "hold_l": 80, "hold_r": 75}]

    def test_parse_equalizer(self):
        result = parse_response("Equalizer 1 0 -2 3 0 1\r")
        assert result == [{"type": "Equalizer", "enabled": True, "bands": [0, -2, 3, 0, 1]}]

    def test_parse_config(self):
        result = parse_response("Config 5\r")
        assert result == [{"type": "Config", "version": 5}]

    def test_parse_msg(self):
        result = parse_response("Msg AF_Peak\r")
        assert result == [{"type": "Msg", "text": "AF_Peak", "af_peak": True}]

    def test_parse_msg_no_peak(self):
        result = parse_response("Msg OK\r")
        assert result == [{"type": "Msg", "text": "OK", "af_peak": False}]

    def test_parse_multiline(self):
        data = "AF 100 90 50 40\rStates 0 0\rConfig 3\r"
        result = parse_response(data)
        assert len(result) == 3
        assert result[0]["type"] == "AF"
        assert result[1]["type"] == "States"
        assert result[2]["type"] == "Config"

    def test_parse_empty_line_skipped(self):
        result = parse_response("\r\r")
        assert result == []

    def test_parse_unknown_line(self):
        result = parse_response("SomethingNew 123\r")
        assert result == [{"type": "Unknown", "raw": "SomethingNew 123"}]

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

    def test_parse_lockmode_no_value_does_not_crash(self):
        result = parse_response("LockMode\r")
        # Should not raise IndexError; should return empty (skipped) or unknown
        assert isinstance(result, list)
