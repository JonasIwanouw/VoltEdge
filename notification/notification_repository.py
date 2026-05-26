# notification/notification_repository.py
# Repository: NotificationRepository
# Bounded Context: Notification

import mysql.connector
import os
from dotenv import load_dotenv
from notification.alert_notification import AlertNotification

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


class NotificationRepository:
    """
    Repository for AlertNotification aggregate root.
    Eneste sted hvor SQL mod alert_notification tabellen må skrives.
    """

    def save(self, notification: AlertNotification):
        """Gem en ny notifikation"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO alert_notification
            (id, incident_id, channel, recipient, delivery_status)
            VALUES (%s, %s, %s, %s, %s)""",
            (notification.id, notification.incident_id,
             notification.channel, notification.recipient,
             notification.delivery_status)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def get_all(self) -> list:
        """Hent alle notifikationer med incident info"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT an.*, i.incident_type, i.severity
            FROM alert_notification an
            JOIN incident i ON an.incident_id = i.id
            ORDER BY an.sent_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    def update_status(self, notification_id: str, status: str):
        """Opdater leveringsstatus"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE alert_notification SET delivery_status = %s WHERE id = %s",
            (status, notification_id)
        )
        conn.commit()
        cursor.close()
        conn.close()