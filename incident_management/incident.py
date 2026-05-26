# incident_management/incident.py
# Aggregate Root: Incident
# Bounded Context: Incident Management

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ==============================================================
# VALUE OBJECTS
# ==============================================================

@dataclass(frozen=True)
class Severity:
    """
    Value Object: Alvorlighed af et incident.
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
    Value Object: Type af fejlhændelse.
    Definerer ubiquitous language for fejltyper.
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
        return self.code == "GRID_OUTAGE"


# ==============================================================
# AGGREGATE ROOT: Incident
# ==============================================================

class Incident:
    """
    Aggregate Root: Incident
    Bounded Context: Incident Management

    Ansvarlig for incident livscyklus:
    Open → Assigned → Ongoing → Resolved

    Domain Events der publiceres:
    - IncidentCreated  (ved oprettelse)
    - IncidentAssigned (når tekniker accepterer)
    - IncidentOngoing  (når tekniker er i gang)
    - IncidentResolved (når incident er løst)
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
        Tekniker har accepteret — skift til Assigned.
        Kaldes når TechnicianAssignment.accept() er kaldt.
        """
        if self.status != "Open":
            raise ValueError(
                f"Kan kun assignere et Open incident. Status: {self.status}"
            )
        self.status = "Assigned"

    def set_ongoing(self):
        """
        Tekniker er i gang med reparation.
        """
        if self.status not in ["Assigned", "Open"]:
            raise ValueError(
                f"Kan kun sætte Ongoing fra Assigned eller Open. Status: {self.status}"
            )
        self.status = "Ongoing"

    def resolve(self):
        """
        Tekniker har løst problemet — luk incident.
        MTTR kan beregnes efter dette kald.
        """
        if self.status not in ["Assigned", "Ongoing"]:
            raise ValueError(
                f"Kan kun resolve et Assigned eller Ongoing incident. Status: {self.status}"
            )
        self.status = "Resolved"
        self.resolved_at = datetime.now()

    def is_resolved(self) -> bool:
        return self.status == "Resolved"

    def is_open(self) -> bool:
        return self.status == "Open"

    def mttr_minutes(self) -> Optional[float]:
        """
        Beregn Mean Time To Repair i minutter.
        Returnerer None hvis incident ikke er resolved.
        """
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.detected_at
        return round(delta.total_seconds() / 60, 2)

    def requires_immediate_action(self) -> bool:
        return self.severity.requires_immediate_action()