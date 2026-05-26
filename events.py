# events.py
# Domain Events
# Eksplicitte hændelser der sker i systemet
# Aggregater kommunikerer via events — ikke direkte med hinanden

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AnomalyDetected:
    """
    Event: Udløses når Charger aggregatet detekterer en anomali.
    Trigger for oprettelse af Incident.
    """
    charger_id: str
    incident_type: str
    severity: str
    temperature: float
    voltage: float
    current_a: float
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class IncidentCreated:
    """
    Event: Udløses når et nyt incident oprettes.
    Trigger for oprettelse af TechnicianAssignment og AlertNotification.
    """
    incident_id: str
    charger_id: str
    incident_type: str
    severity: str
    root_cause_recommendation: str = None
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class AssignmentCreated:
    """
    Event: Udløses når en teknikertildeling oprettes.
    """
    assignment_id: str
    incident_id: str
    technician_id: str
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class AssignmentAccepted:
    """
    Event: Udløses når tekniker accepterer en opgave.
    Trigger for at opdatere Incident status til Assigned.
    """
    assignment_id: str
    incident_id: str
    technician_id: str
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class AssignmentRejected:
    """
    Event: Udløses når tekniker afviser en opgave.
    Incident forbliver Open.
    """
    assignment_id: str
    incident_id: str
    technician_id: str
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class IncidentAssigned:
    """
    Event: Udløses når incident skifter til Assigned.
    """
    incident_id: str
    technician_id: str
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class IncidentOngoing:
    """
    Event: Udløses når tekniker er i gang med reparation.
    """
    incident_id: str
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class IncidentResolved:
    """
    Event: Udløses når incident er løst.
    Indeholder MTTR til statistik og Power BI.
    """
    incident_id: str
    mttr_minutes: float = None
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass
class NotificationCreated:
    """
    Event: Udløses når en notifikation sendes til tekniker.
    """
    notification_id: str
    incident_id: str
    channel: str
    recipient: str
    occurred_at: datetime = field(default_factory=datetime.now)