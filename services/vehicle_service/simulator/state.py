from dataclasses import dataclass, field

@dataclass
class VehicleSimState:
    speed_kph: float = 0.0
    gear: str = "P"
    windows: dict = field(default_factory=lambda: {"FL": 0, "FR": 0, "RL": 0, "RR": 0})
    ac: dict = field(default_factory=lambda: {
        "ac_on": True, "temp_c": 24.0, "fan_level": 2, "mode": "auto", "recirc_on": False
    })

STATE = VehicleSimState()