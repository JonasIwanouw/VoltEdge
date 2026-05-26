# domain.py
# VoltEdge Mobility A/S — Domain Model
# Implementeret efter Domain Driven Design principper
#
# Indeholder:
#   - Value Objects: Temperature, Voltage, Current, Severity, IncidentType
#   - Entiteter: TelemetryReading, TechnicianAssignment, AlertNotification
#   - Aggregate Roots: Charger, Incident

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ==============================================================
# VALUE OBJECTS
# Definition: Ingen identitet — defineres udelukkende af deres
# værdier. To Temperature objekter med samme celsius er identiske.
# ==============================================================

@dataclass(frozen=True)
class Temperature:
    """
    Value Object: Repræsenterer en temperaturmåling i celsius.
    Indeholder domænelogik for hvornår temperaturen er unormal.
    Ubiquitous language: 'temperature', 'critical', 'risk_level'
    """
    celsius: float

    def __post_init__(self):
        if self.celsius < -50 or self.celsius > 300:
            raise ValueError(f"Ugyldig temperatur: {self.celsius}°C")

    def is_critical(self) -> bool:
        """Returnerer True hvis temperaturen overstiger threshold på 80°C"""
        return self.celsius > 80.0

    def risk_level(self) -> str:
        """Beregner risikoniveau baseret på temperatur"""
        if self.celsius > 70:
            return "HØJ"
        if self.celsius > 55:
            return "MEDIUM"
        return "LAV"


@dataclass(frozen=True)
class Voltage:
    """
    Value Object: Repræsenterer spændingsmåling i volt.
    Normal spænding er mellem 200-250V i det danske elnet.
    """
    volts: float

    def is_normal(self) -> bool:
        """Returnerer True hvis spænding er over minimumstærskel"""
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
    Value Object: Repræsenterer strømstyrke i ampere.
    Bruges til at detektere ledningsskade — ingen strøm
    trods normal spænding indikerer CABLE_DEFECT.
    """
    ampere: float

    def is_flowing(self) -> bool:
        """Returnerer True hvis der trækkes strøm"""
        return self.ampere >= 0.1


@dataclass(frozen=True)
class Severity:
    """
    Value Object: Repræsenterer alvorlighed af et incident.
    Styrer prioritering af teknikerudsendelse.
    """
    level: str

    LEVELS = ["Low", "Medium", "High", "Critical"]

    def __post_init__(self):
        if self.level not in self.LEVELS:
            raise ValueError(f"Ugyldig severity: {self.level}")

    def is_critical(self) -> bool:
        return self.level == "Critical"

    def requires_immediate_action(self) -> bool:
        return self.level in ["High", "Critical"]


@dataclass(frozen=True)
class IncidentType:
    """
    Value Object: Repræsenterer typen af en fejlhændelse.
    Definerer ubiquitous language for fejltyper i systemet.
    """
    code: str

    VALID_TYPES = [
        "OVER_TEMPERATURE",
        "NO_POWER",
        "CABLE_DEFECT",
        "CONNECTOR_FAULT",
        "GRID_OUTAGE"
    ]

    def __post_init__(self):
        if self.code not in self.VALID_TYPES:
            raise ValueError(f"Ugyldig incident type: {self.code}")

    def is_grid_related(self) -> bool:
        """Grid-relaterede fejl er ikke VoltEdges ansvar"""
        return self.code == "GRID_OUTAGE"


# ==============================================================
# ENTITETER
# Definition: Har identitet — to incidents med samme data
# er IKKE ens fordi de har forskellige IDs.
# ==============================================================

class TelemetryReading:
    """
    Entitet under Charger aggregatet.
    Repræsenterer én telemetrimåling fra en ladestander.
    Ejes af Charger aggregate root — tilgås aldrig direkte.
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "charger_id": self.charger_id,
            "power_kw": self.power_kw,
            "voltage": self.voltage.volts,
            "current_a": self.current_a.ampere,
            "temperature": self.temperature.celsius,
            "recorded_at": self.recorded_at,
            "error_code": self.error_code
        }


class TechnicianAssignment:
    """
    Entitet under Incident aggregatet.
    Repræsenterer en teknikers tildeling til et incident.
    Håndterer accept/afvis logik.
    """
    def __init__(self, id: str, incident_id: str,
                 technician_id: str):
        self.id = id
        self.incident_id = incident_id
        self.technician_id = technician_id
        self.confirmed = False
        self.proposed_slot = None
        self.assigned_at = datetime.now()

    def accept(self):
        """Tekniker accepterer opgaven"""
        self.confirmed = True

    def reject(self):
        """Tekniker afviser opgaven"""
        self.confirmed = False

    def propose_slot(self, slot: datetime):
        """Foreslå en ledig tid i teknikerens kalender"""
        self.proposed_slot = slot


class AlertNotification:
    """
    Entitet under Incident aggregatet.
    Repræsenterer en notifikation sendt til tekniker.
    """
    def __init__(self, id: str, incident_id: str,
                 channel: str, recipient: str):
        self.id = id
        self.incident_id = incident_id
        self.channel = channel
        self.recipient = recipient
        self.delivery_status = "Pending"
        self.sent_at = datetime.now()

    def mark_delivered(self):
        """Marker notifikation som leveret"""
        self.delivery_status = "Delivered"

    def mark_failed(self):
        """Marker notifikation som fejlet"""
        self.delivery_status = "Failed"


# ==============================================================
# AGGREGATE ROOTS
# Definition: Eneste indgang til aggregatet udefra.
# Al forretningslogik lever her — ikke i API-laget.
# ==============================================================

class Charger:
    """
    Aggregate Root: Charger (Device Management bounded context)
    
    Ansvarlig for:
    - Repræsentation af en fysisk ladestander
    - Detektion af anomalier i telemetri-målinger
    - Klassificering af fejltype og severity
    
    Ubiquitous language: 'charger', 'anomaly', 'detect'
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
        Kernedomænelogik: Analyserer en telemetrimåling
        og returnerer (IncidentType, Severity) eller (None, None)

        Rækkefølge:
        1. Temperatur — kritisk fejl, behandles først
        2. Voltage — tjek grid status før incident oprettes
        3. Current — ledningsskade hvis strøm mangler
        4. Error code — OCPP rapporteret fejl
        """
        if reading.temperature.is_critical():
            return (
                IncidentType("OVER_TEMPERATURE"),
                Severity("Critical")
            )

        if not reading.voltage.is_normal():
            if grid_status == "GRID_STRESS":
                return (
                    IncidentType("GRID_OUTAGE"),
                    Severity("High")
                )
            return (
                IncidentType("NO_POWER"),
                Severity("High")
            )

        if not reading.current_a.is_flowing() and reading.voltage.is_normal():
            return (
                IncidentType("CABLE_DEFECT"),
                Severity("Medium")
            )

        if reading.has_error():
            return (
                IncidentType("CONNECTOR_FAULT"),
                Severity("Medium")
            )

        return None, None

    def is_faulted(self) -> bool:
        return self.status == "faulted"

    def is_available(self) -> bool:
        return self.status == "available"


class Incident:
    """
    Aggregate Root: Incident (Incident Management bounded context)

    Ansvarlig for:
    - Incident livscyklus: Open → Assigned → Ongoing → Resolved
    - Validering af lovlige tilstandsskift
    - Beregning af MTTR (Mean Time To Repair)

    Ubiquitous language: 'incident', 'resolve', 'assign', 'ongoing'
    """
    def __init__(self, id: str, charger_id: str,
                 incident_type: IncidentType,
                 severity: Severity,
                 root_cause_recommendation: str = None):
        self.id = id
        self.charger_id = charger_id
        self.incident_type = incident_type
        self.severity = severity
        self.status = "Open"
        self.detected_at = datetime.now()
        self.resolved_at = None
        self.root_cause_recommendation = root_cause_recommendation

    def assign(self):
        """
        Tekniker har accepteret opgaven.
        Incident skifter fra Open til Assigned.
        """
        if self.status != "Open":
            raise ValueError(
                f"Kan kun assignere et Open incident. "
                f"Nuværende status: {self.status}"
            )
        self.status = "Assigned"

    def set_ongoing(self):
        """
        Tekniker er på vej eller i gang med reparation.
        Incident skifter til Ongoing.
        """
        if self.status not in ["Assigned", "Open"]:
            raise ValueError(
                f"Kan kun sætte Ongoing fra Assigned eller Open. "
                f"Nuværende status: {self.status}"
            )
        self.status = "Ongoing"

    def resolve(self):
        """
        Tekniker har løst problemet.
        Incident lukkes og MTTR kan beregnes.
        """
        if self.status not in ["Assigned", "Ongoing"]:
            raise ValueError(
                f"Kan kun resolve et Assigned eller Ongoing incident. "
                f"Nuværende status: {self.status}"
            )
        self.status = "Resolved"
        self.resolved_at = datetime.now()

    def is_resolved(self) -> bool:
        return self.status == "Resolved"

    def is_open(self) -> bool:
        return self.status == "Open"

    def mttr_minutes(self) -> Optional[float]:
        """
        Beregner Mean Time To Repair i minutter.
        Returnerer None hvis incident ikke er resolved.
        """
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.detected_at
        return round(delta.total_seconds() / 60, 2)

    def requires_immediate_action(self) -> bool:
        """Kritiske og High severity incidents kræver øjeblikkelig handling"""
        return self.severity.requires_immediate_action()