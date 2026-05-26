# notification/alert_notification.py
# Aggregate Root: AlertNotification
# Bounded Context: Notification

from datetime import datetime


class AlertNotification:
    """
    Aggregate Root: AlertNotification
    Bounded Context: Notification

    Ansvarlig for notifikationer sendt til teknikere.
    Håndterer leveringsstatus.
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

    def is_delivered(self) -> bool:
        return self.delivery_status == "Delivered"