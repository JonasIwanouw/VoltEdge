# incident_management/technician_assignment.py
# Aggregate Root: TechnicianAssignment
# Bounded Context: Incident Management

from datetime import datetime


class TechnicianAssignment:
    """
    Aggregate Root: TechnicianAssignment
    Bounded Context: Incident Management

    Ansvarlig for teknikerens relation til et incident.
    Håndterer accept/afvis logik og kalender-booking.

    Livscyklus:
    Pending → Accepted (tekniker accepterer)
    Pending → Rejected (tekniker afviser)
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
        """
        Tekniker accepterer opgaven.
        Trigger: AssignmentAccepted event → Incident skifter til Assigned
        """
        self.confirmed = True

    def reject(self):
        """
        Tekniker afviser opgaven.
        Trigger: AssignmentRejected event → Incident forbliver Open
        """
        self.confirmed = False

    def propose_slot(self, slot: datetime):
        """
        Foreslå ledig tid i teknikerens kalender.
        Fremtidig integration med MS Graph / Outlook API.
        """
        self.proposed_slot = slot

    def is_confirmed(self) -> bool:
        return self.confirmed is True

    def is_pending(self) -> bool:
        return self.confirmed is False