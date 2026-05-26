# incident_management/incident_repository.py
# Repository: IncidentRepository + TechnicianAssignmentRepository
# Bounded Context: Incident Management

import mysql.connector
import os
import uuid
from dotenv import load_dotenv
from incident_management.incident import Incident, IncidentType, Severity
from incident_management.technician_assignment import TechnicianAssignment

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


class IncidentRepository:
    """
    Repository for Incident aggregate root.
    Eneste sted hvor SQL mod incident tabellen må skrives.
    """

    def save(self, incident: Incident):
        """Gem et nyt incident i databasen"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO incident 
            (id, charger_id, incident_type, severity, status, root_cause_recommendation) 
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (incident.id, incident.charger_id,
             incident.incident_type.code,
             incident.severity.level,
             incident.status,
             incident.root_cause_recommendation)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def get(self, incident_id: str) -> Incident:
        """Hent ét incident via ID"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM incident WHERE id = %s", (incident_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return None
        incident = Incident(
            id=row["id"],
            charger_id=row["charger_id"],
            incident_type=IncidentType(row["incident_type"]),
            severity=Severity(row["severity"]),
            root_cause_recommendation=row["root_cause_recommendation"]
        )
        incident.status = row["status"]
        return incident

    def get_all(self) -> list:
        """Hent alle incidents med charger info"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT i.*, c.location, c.vendor
            FROM incident i
            JOIN charger c ON i.charger_id = c.id
            ORDER BY i.detected_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    def update_status(self, incident_id: str, status: str,
                      resolved_at=None):
        """Opdater status på et incident"""
        conn = get_connection()
        cursor = conn.cursor()
        if resolved_at:
            cursor.execute(
                """UPDATE incident 
                SET status = %s, resolved_at = NOW() 
                WHERE id = %s""",
                (status, incident_id)
            )
        else:
            cursor.execute(
                "UPDATE incident SET status = %s WHERE id = %s",
                (status, incident_id)
            )
        conn.commit()
        cursor.close()
        conn.close()

    def update_root_cause(self, incident_id: str,
                          recommendation: str):
        """Opdater root cause anbefaling"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE incident 
            SET root_cause_recommendation = %s 
            WHERE id = %s""",
            (recommendation, incident_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def get_without_root_cause(self) -> list:
        """Hent alle incidents uden root cause anbefaling"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, charger_id 
            FROM incident
            WHERE root_cause_recommendation IS NULL
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows


class TechnicianAssignmentRepository:
    """
    Repository for TechnicianAssignment aggregate root.
    Eneste sted hvor SQL mod technician_assignment tabellen må skrives.
    """

    def save(self, assignment: TechnicianAssignment):
        """Gem en ny teknikertildeling"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO technician_assignment
            (id, incident_id, technician_id, confirmed)
            VALUES (%s, %s, %s, %s)""",
            (assignment.id, assignment.incident_id,
             assignment.technician_id, assignment.confirmed)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def get(self, assignment_id: str) -> TechnicianAssignment:
        """Hent én teknikertildeling via ID"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM technician_assignment WHERE id = %s",
            (assignment_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return None
        assignment = TechnicianAssignment(
            id=row["id"],
            incident_id=row["incident_id"],
            technician_id=row["technician_id"]
        )
        assignment.confirmed = row["confirmed"]
        return assignment

    def get_by_technician(self, technician_id: str) -> list:
        """Hent alle opgaver for en specifik tekniker"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ta.*, i.incident_type, i.severity, c.location
            FROM technician_assignment ta
            JOIN incident i ON ta.incident_id = i.id
            JOIN charger c ON i.charger_id = c.id
            WHERE ta.technician_id = %s
            ORDER BY ta.assigned_at DESC
        """, (technician_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    def get_all(self) -> list:
        """Hent alle teknikertildelinger"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ta.*, i.incident_type, i.severity, c.location
            FROM technician_assignment ta
            JOIN incident i ON ta.incident_id = i.id
            JOIN charger c ON i.charger_id = c.id
            ORDER BY ta.assigned_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    def update_confirmed(self, assignment_id: str,
                         confirmed: bool):
        """Opdater om tekniker har accepteret"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE technician_assignment SET confirmed = %s WHERE id = %s",
            (confirmed, assignment_id)
        )
        conn.commit()
        cursor.close()
        conn.close()