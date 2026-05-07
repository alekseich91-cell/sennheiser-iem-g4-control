def build_command(command: str, *args) -> str:
    parts = [command] + [str(a) for a in args]
    return " ".join(parts) + "\r"


def parse_response(data: str) -> list[dict]:
    results = []
    for line in data.split("\r"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ")
        keyword = parts[0]

        if keyword == "Name":
            results.append({"type": "Name", "value": parts[1] if len(parts) > 1 else ""})
        elif keyword == "Frequency":
            results.append({"type": "Frequency", "value": int(parts[1])})
        elif keyword == "Sensitivity":
            results.append({"type": "Sensitivity", "value": int(parts[1])})
        elif keyword == "Mode":
            results.append({"type": "Mode", "value": "stereo" if parts[1] == "1" else "mono"})
        elif keyword == "States":
            results.append({"type": "States", "mute": parts[1] == "1", "flags": int(parts[2])})
        elif keyword == "AF":
            results.append({
                "type": "AF",
                "peak_l": int(parts[1]),
                "peak_r": int(parts[2]),
                "hold_l": int(parts[3]),
                "hold_r": int(parts[4]),
            })
        elif keyword == "Equalizer":
            results.append({
                "type": "Equalizer",
                "enabled": parts[1] == "1",
                "bands": [int(parts[i]) for i in range(2, 7)],
            })
        elif keyword == "Config":
            results.append({"type": "Config", "version": int(parts[1])})
        elif keyword == "Msg":
            text = " ".join(parts[1:])
            results.append({"type": "Msg", "text": text, "af_peak": "AF_Peak" in text})
        elif keyword == "RF":
            results.append({"type": "RF", "value": parts[1] if len(parts) > 1 else ""})
        elif keyword == "LockMode":
            results.append({"type": "LockMode", "value": parts[1] == "1"})
        elif keyword == "Identify":
            results.append({"type": "Identify"})
        else:
            results.append({"type": "Unknown", "raw": line})

    return results
