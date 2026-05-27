# device_management/charger.py
# Aggregate Root: Charger
# Bounded Context: Device Management

from dataclasses import dataclass
from typing import Optional


# ==============================================================
# VALUE OBJECTS
# ==============================================================

@dataclass(frozen=True)
class Temperature:
    """
    Value Object: Temperaturmåling i celsius.
    Indeholder domænelogik for hvornår temperaturen er unormal.
    """
    celsius: float

    def __post_init__(self):
        if self.celsius < -30 or self.celsius > 120:
            raise ValueError(f"Ugyldig temperatur: {self.celsius}°C — skal være mellem -30°C og 120°C")

    def is_critical(self) -> bool:
        return self.celsius > 80.0

    def risk_level(self) -> str:
        if self.celsius > 70:
            return "HØJ"
        if self.celsius > 55:
            return "MEDIUM"
        return "LAV"


@dataclass(frozen=True)
class Voltage:
    """
    Value Object: Spændingsmåling i volt.
    Normal spænding er mellem 200-1000V (AC og DC ladere).
    """
    volts: float

    def __post_init__(self):
        if self.volts < 0 or self.volts > 1000:
            raise ValueError(f"Ugyldig voltage: {self.volts}V — skal være mellem 0V og 1000V")

    def is_normal(self) -> bool:
        return self.volts >= 200.0

    def risk_level(self) -> str:
        if self.volts < 180:
            return "HØJ"
        if self.volts < 200:
            return "MEDIUM"
        return "LAV"


@dataclass(frozen=True)
class Current:
    """
    Value Object: Strømstyrke i ampere.
    Max 500A dækker både AC og DC hurtigladere.
    """
    ampere: float

    def __post_init__(self):
        if self.ampere < 0 or self.ampere > 500:
            raise ValueError(f"Ugyldig strømstyrke: {self.ampere}A — skal være mellem 0A og 500A")

    def is_flowing(self) -> bool:
        return self.ampere >= 0.1


# ==============================================================
# ENTITET
# ==============================================================

class TelemetryReading:
    """
    Entitet under Charger aggregatet.
    Ejes af Charger — tilgås aldrig direkte udefra.
    """
    def __init__(self, id: str, charger_id: str,
                 power_kw: float, voltage: float,
                 current_a: float, temperature: float,
                 recorded_at: str, error_code: str = None):
        self.id = id
        self.charger_id = charger_id
        self.power_kw = power_kw
        self.voltage = Voltage(voltage)
        self.current_a = Current(current_a)
        self.temperature = Temperature(temperature)
        self.recorded_at = recorded_at
        self.error_code = error_code

    def has_error(self) -> bool:
        return self.error_code is not None


# ==============================================================
# AGGREGATE ROOT
# ==============================================================

class Charger:
    """
    Aggregate Root: Charger
    Bounded Context: Device Management

    Ansvarlig for detektion af anomalier i telemetrimålinger.
    Al anomaly detection logik lever her — ikke i API-laget.
    """
    def __init__(self, id: str, location: str,
                 vendor: str, model: str,
                 firmware: str, status: str):
        self.id = id
        self.location = location
        self.vendor = vendor
        self.model = model
        self.firmware = firmware
        self.status = status

    def detect_anomaly(self, reading: TelemetryReading,
                       grid_status: str = "GRID_OK") -> tuple:
        """
        Kernedomænelogik: Analyserer telemetrimåling
        og returnerer (incident_type_str, severity_str) eller (None, None)
        """
        if reading.temperature.is_critical():
            return "OVER_TEMPERATURE", "Critical"

        if not reading.voltage.is_normal():
            if grid_status == "GRID_STRESS":
                return "GRID_OUTAGE", "High"
            return "NO_POWER", "High"

        if not reading.current_a.is_flowing() and reading.voltage.is_normal():
            return "CABLE_DEFECT", "Medium"

        if reading.has_error():
            return "CONNECTOR_FAULT", "Medium"

        return None, None

    def is_faulted(self) -> bool:
        return self.status == "faulted"

    def is_available(self) -> bool:
        return self.status == "available"