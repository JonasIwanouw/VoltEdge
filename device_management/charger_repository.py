# device_management/charger_repository.py
# Repository: ChargerRepository
# Bounded Context: Device Management
#
# Ansvarlig for at hente og gemme Charger aggregater fra databasen.
# API-laget må aldrig skrive SQL direkte — det går altid via repository.

import mysql.connector
import os
from dotenv import load_dotenv
from device_management.charger import Charger, TelemetryReading

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


class ChargerRepository:
    """
    Repository for Charger aggregate root.
    Eneste sted hvor SQL mod charger og telemetry_reading tabellerne må skrives.
    """

    def get(self, charger_id: str) -> Charger:
        """Hent én ladestander via ID"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM charger WHERE id = %s", (charger_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return None
        return Charger(
            id=row["id"],
            location=row["location"],
            vendor=row["vendor"],
            model=row["model"],
            firmware=row["firmware"],
            status=row["status"]
        )

    def get_all(self) -> list:
        """Hent alle ladestandere"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM charger")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [Charger(
            id=r["id"],
            location=r["location"],
            vendor=r["vendor"],
            model=r["model"],
            firmware=r["firmware"],
            status=r["status"]
        ) for r in rows]

    def save_telemetry(self, reading: TelemetryReading):
        """Gem en telemetrimåling tilhørende en Charger"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO telemetry_reading 
            (id, charger_id, power_kw, voltage, current_a, temperature, error_code, recorded_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (reading.id, reading.charger_id,
             reading.power_kw, reading.voltage.volts,
             reading.current_a.ampere, reading.temperature.celsius,
             reading.error_code, reading.recorded_at)
        )
        conn.commit()
        cursor.close()
        conn.close()