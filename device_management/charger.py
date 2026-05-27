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
    
    Ingen hard validering — ekstreme værdier er symptomer på fejl.
    Eksempler:
    - Under -30°C → sensor fejl eller ekstrem kulde
    - Over 120°C  → kølesystem fejl eller brand risiko
    Begge skal generere incidents frem for at crashe systemet.
    """
    celsius: float

    def is_critical(self) -> bool:
        """Over 80°C er kritisk for en EV-ladestandere"""
        return self.celsius > 80.0

    def is_sensor_fault(self) -> bool:
        """Under -30°C indikerer sandsynligvis en defekt sensor"""
        return self.celsius < -30.0

    def risk_level(self) -> str:
        if self.celsius > 70 or self.celsius < -30:
            return "HØJ"
        if self.celsius > 55:
            return "MEDIUM"
        return "LAV"


@dataclass(frozen=True)
class Voltage:
    """
    Value Object: Spændingsmåling i volt.
    
    Ingen hard validering — ekstreme værdier er symptomer på fejl.
    Eksempler:
    - Under 0V   → sensor fejl eller kortslutning
    - Over 1000V → overspænding (CCS2 max er 1000V)
    Begge skal generere incidents frem for at crashe systemet.
    """
    volts: float

    def is_normal(self) -> bool:
        """Normal AC spænding er minimum 200V"""
        return self.volts >= 200.0

    def is_overvoltage(self) -> bool:
        """Over 1000V indikerer farlig overspænding"""
        return self.volts > 1000.0

    def is_sensor_fault(self) -> bool:
        """Negative værdier indikerer sensor fejl"""
        return self.volts < 0.0

    def risk_level(self) -> str:
        if self.volts < 0 or self.volts > 1000:
            return "HØJ"
        if self.volts < 180:
            return "HØJ"
        if self.volts < 200:
            return "MEDIUM"
        return "LAV"


@dataclass(frozen=True)
class Current:
    """
    Value Object: Strømstyrke i ampere.
    
    Ingen hard validering — ekstreme værdier er symptomer på fejl.
    Eksempler:
    - Over 500A → kortslutning eller overbelastning
    - Negativ   → sensor fejl
    Begge skal generere incidents frem for at crashe systemet.
    """
    ampere: float

    def is_flowing(self) -> bool:
        """Strøm flyder hvis over 0.1A"""
        return self.ampere >= 0.1

    def is_overcurrent(self) -> bool:
        """Over 500A indikerer kortslutning"""
        return self.ampere > 500.0

    def is_sensor_fault(self) -> bool:
        """Negative værdier indikerer sensor fejl"""
        return self.ampere < 0.0


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

    Detektionsrækkefølge:
    1. Sensor fejl (ekstreme værdier udenfor fysisk mulige grænser)
    2. Temperatur (kritisk sikkerhedsfejl)
    3. Overspænding/overstrøm (kritisk sikkerhedsfejl)
    4. Ingen strøm (driftsfejl)
    5. Ledningsskade (driftsfejl)
    6. OCPP fejlkode (connector fejl)
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

        # ---------- SENSOR FEJL ----------
        # Ekstreme værdier udenfor fysisk mulige grænser
        # indikerer defekt sensor der skal udskiftes
        if reading.temperature.is_sensor_fault():
            return "OVER_TEMPERATURE", "Critical"

        if reading.voltage.is_sensor_fault():
            return "NO_POWER", "High"

        if reading.current_a.is_sensor_fault():
            return "CABLE_DEFECT", "Medium"

        # ---------- KRITISKE FEJL ----------
        # Høj temperatur — risiko for brand
        if reading.temperature.is_critical():
            return "OVER_TEMPERATURE", "Critical"

        # Overspænding — risiko for skade på hardware
        if reading.voltage.is_overvoltage():
            return "NO_POWER", "High"

        # Overstrøm — risiko for kortslutning
        if reading.current_a.is_overcurrent():
            return "CABLE_DEFECT", "Critical"

        # ---------- DRIFTSFEJL ----------
        # Ingen strøm fra nettet
        if not reading.voltage.is_normal():
            if grid_status == "GRID_STRESS":
                return "GRID_OUTAGE", "High"
            return "NO_POWER", "High"

        # Ledningsskade — strøm flyder ikke trods normal spænding
        if not reading.current_a.is_flowing() and reading.voltage.is_normal():
            return "CABLE_DEFECT", "Medium"

        # OCPP rapporteret connector fejl
        if reading.has_error():
            return "CONNECTOR_FAULT", "Medium"

        return None, None

    def is_faulted(self) -> bool:
        return self.status == "faulted"

    def is_available(self) -> bool:
        return self.status == "available"