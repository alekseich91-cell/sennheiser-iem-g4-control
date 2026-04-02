from dataclasses import dataclass, field


@dataclass
class IEMDevice:
    ip: str
    name: str = ""
    frequency: int = 0          # kHz, e.g. 514125 = 514.125 MHz
    sensitivity: int = -18      # 0 to -42 in steps of 3
    mute: bool = False
    mode: str = "stereo"        # "mono" or "stereo"
    eq: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    audio_level_l: int = 0      # 0-255 peak level
    audio_level_r: int = 0
    audio_hold_l: int = 0
    audio_hold_r: int = 0
    online: bool = False
    _missed_pushes: int = field(default=0, repr=False)

    @property
    def frequency_mhz(self) -> str:
        raw = str(self.frequency).zfill(6)
        return f"{raw[:3]}.{raw[3:]}"

    # Allowed sensitivity values for reference
    SENSITIVITY_VALUES = list(range(0, -45, -3))  # [0, -3, -6, ..., -42]
