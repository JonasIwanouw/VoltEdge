import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

# ---------- DATABASE FORBINDELSE ----------

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# Thresholds — samme som i app.py
TEMP_THRESHOLD = 80.0
VOLTAGE_MIN = 200.0
CURRENT_MIN = 0.1

# ---------- ANBEFALING ----------

def get_recommendation(root_cause, temp_trend, voltage_trend, current_trend, is_recurring):
    if is_recurring:
        return "Strukturelt problem — ladestander bør udskiftes eller gennemgå dybere inspektion"
    if root_cause == "OVER_TEMPERATURE":
        if temp_trend == "STIGENDE":
            return "Kritisk — send tekniker øjeblikkeligt, kølesystem fejler"
        return "Send tekniker — temperaturproblem detekteret"
    if root_cause == "NO_POWER":
        if voltage_trend == "FALDENDE":
            return "Spænding er faldende — tjek el-tilslutning og sikringer på lokationen"
        return "Ingen strøm fra nettet — tjek el-tilslutning"
    if root_cause == "CABLE_DEFECT":
        if current_trend == "FALDENDE":
            return "Strømstyrke faldende trods normal spænding — kabeludskiftning nødvendig"
        return "Kabelskade detekteret — send tekniker"
    return "Ingen kritiske fejl — fortsæt overvågning"

# ---------- ANALYSE AF ÉN LADESTANDER ----------

def analyze_charger(charger_id):
    """
    Analyserer en ladestanders telemetri-historik
    og identificerer den sandsynlige årsag til fejl
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Hent de seneste 10 målinger
    cursor.execute("""
        SELECT power_kw, voltage, current_a, temperature, error_code, recorded_at
        FROM telemetry_reading
        WHERE charger_id = %s
        ORDER BY recorded_at DESC
        LIMIT 10
    """, (charger_id,))
    readings = cursor.fetchall()

    if not readings:
        cursor.close()
        conn.close()
        return {"error": "Ingen telemetri data fundet"}

    # ---------- TEMPERATUR TREND ----------
    temps = [r["temperature"] for r in readings]
    temp_trend = "STIGENDE" if temps[0] > temps[-1] else "FALDENDE" if temps[0] < temps[-1] else "STABIL"
    temp_risk = "HØJ" if temps[0] > 70 else "MEDIUM" if temps[0] > 55 else "LAV"

    # ---------- VOLTAGE TREND ----------
    voltages = [r["voltage"] for r in readings]
    voltage_trend = "FALDENDE" if voltages[0] < voltages[-1] else "STIGENDE" if voltages[0] > voltages[-1] else "STABIL"
    voltage_risk = "HØJ" if voltages[0] < 180 else "MEDIUM" if voltages[0] < 200 else "LAV"

    # ---------- CURRENT TREND ----------
    currents = [r["current_a"] for r in readings]
    current_trend = "FALDENDE" if currents[0] < currents[-1] else "STIGENDE" if currents[0] > currents[-1] else "STABIL"
    current_risk = "HØJ" if currents[0] < CURRENT_MIN and voltages[0] >= VOLTAGE_MIN else "LAV"

    # ---------- RECURRING INCIDENTS ----------
    cursor.execute("""
        SELECT incident_type, COUNT(*) as antal
        FROM incident
        WHERE charger_id = %s
        AND detected_at >= NOW() - INTERVAL 7 DAY
        GROUP BY incident_type
    """, (charger_id,))
    recurring = cursor.fetchall()
    is_recurring = any(r["antal"] > 1 for r in recurring)

    # ---------- DOMINERENDE FEJLTYPE ----------
    error_counts = {}
    for r in readings:
        if r["error_code"]:
            error_counts[r["error_code"]] = error_counts.get(r["error_code"], 0) + 1

    root_cause = max(error_counts, key=error_counts.get) if error_counts else None

    # ---------- MTTR ----------
    cursor.execute("""
        SELECT AVG(TIMESTAMPDIFF(MINUTE, detected_at, resolved_at)) as avg_mttr
        FROM incident
        WHERE charger_id = %s
        AND resolved_at IS NOT NULL
    """, (charger_id,))
    mttr_result = cursor.fetchone()
    avg_mttr = mttr_result["avg_mttr"] if mttr_result["avg_mttr"] else None

    cursor.close()
    conn.close()

    return {
        "charger_id": charger_id,
        "temperature_analysis": {
            "current_temp": temps[0],
            "trend": temp_trend,
            "risk_level": temp_risk
        },
        "voltage_analysis": {
            "current_voltage": voltages[0],
            "trend": voltage_trend,
            "risk_level": voltage_risk
        },
        "current_analysis": {
            "current_a": currents[0],
            "trend": current_trend,
            "risk_level": current_risk
        },
        "recurring_incidents": {
            "is_recurring": is_recurring,
            "incidents_last_7_days": recurring
        },
        "root_cause": root_cause,
        "avg_mttr_minutes": avg_mttr,
        "recommendation": get_recommendation(
            root_cause, temp_trend, voltage_trend, current_trend, is_recurring
        )
    }

# ---------- MTTR STATISTIK ----------

def get_mttr_stats():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            incident_type,
            COUNT(*) as total_incidents,
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved,
            SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_incidents,
            AVG(TIMESTAMPDIFF(MINUTE, detected_at, resolved_at)) as avg_mttr_minutes
        FROM incident
        GROUP BY incident_type
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

# ---------- INCIDENT STATISTIK ----------

def get_incident_stats():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            incident_type,
            severity,
            COUNT(*) as antal,
            SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_incidents,
            SUM(CASE WHEN status = 'Assigned' THEN 1 ELSE 0 END) as assigned,
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved
        FROM incident
        GROUP BY incident_type, severity
        ORDER BY antal DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
