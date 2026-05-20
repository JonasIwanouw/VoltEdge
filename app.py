from flask import Flask, jsonify, request
import mysql.connector
import os
import uuid
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---------- DATABASE FORBINDELSE ----------

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# ---------- THRESHOLDS ----------

TEMP_THRESHOLD = 80.0      # grader celsius
VOLTAGE_MIN = 200.0        # volt — under dette = ingen strøm fra nettet
CURRENT_MIN = 0.1          # ampere — under dette = ingen strøm trækkes

# ---------- ENERGINET GRID CHECK ----------

def check_grid_status(area="DK1"):
    """
    Kalder Energinet API og tjekker om el-nettet er stabilt.
    area = DK1 (Jylland/Fyn) eller DK2 (Sjælland)
    Returnerer: GRID_OK, GRID_STRESS eller GRID_UNKNOWN
    """
    try:
        url = "https://electricitymarketservice.energinet.dk/api/v1/PublicData/dataset/mfrrrequest/latest"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            values = data.get("mfrrRequest", [{}])[0].get("values", [])
            for v in values:
                if v.get("area") == area and v.get("value", 0) > 500:
                    return "GRID_STRESS"
            return "GRID_OK"
        return "GRID_UNKNOWN"
    except:
        return "GRID_UNKNOWN"

# ---------- BASIC ROUTES ----------

@app.route("/ping", methods=["GET"])
def ping():
    return "pong from VoltEdge Incident Management API"

@app.route("/")
def index():
    return "VoltEdge API kører. Prøv /api/chargers eller /api/incidents"

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

# ---------- CHARGERS API ----------

@app.route("/api/chargers", methods=["GET"])
def get_chargers():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM charger")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/chargers/<string:charger_id>", methods=["GET"])
def get_charger(charger_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM charger WHERE id = %s", (charger_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return jsonify(row)
    return jsonify({"error": "Charger not found"}), 404

# ---------- TELEMETRI API ----------

@app.route("/api/telemetry", methods=["POST"])
def receive_telemetry():
    data = request.get_json()

    # Tjek at alle nødvendige felter er med
    required_fields = ["id", "charger_id", "power_kw", "voltage", "current_a", "temperature"]
    if not data or any(f not in data for f in required_fields):
        return jsonify({"error": f"Missing one of {required_fields}"}), 400

    # Hent alle målinger fra requesten
    power_kw    = data["power_kw"]
    voltage     = data["voltage"]
    current_a   = data["current_a"]
    temperature = data["temperature"]
    error_code  = data.get("error_code", None)
    grid_status = None

    # ---------- INCIDENT DETECTION LOGIK ----------

    detected_incident = None
    severity = None

    if temperature > TEMP_THRESHOLD:
        # Temperatur over 80 grader — kritisk fejl
        detected_incident = "OVER_TEMPERATURE"
        severity = "Critical"
        error_code = "OVER_TEMPERATURE"

    elif voltage < VOLTAGE_MIN:
        # Spænding under 200V — tjek om det er el-nettets fejl
        grid_status = check_grid_status("DK1")

        if grid_status == "GRID_STRESS":
            # El-nettet er under stress — ikke VoltEdges ansvar
            detected_incident = "GRID_OUTAGE"
            severity = "High"
            error_code = "GRID_OUTAGE"
        else:
            # El-nettet er OK — fejlen er hos ladestanderen
            detected_incident = "NO_POWER"
            severity = "High"
            error_code = "NO_POWER"

    elif current_a < CURRENT_MIN and voltage >= VOLTAGE_MIN:
        # Spænding er normal men ingen strøm trækkes — ledningsskade
        detected_incident = "CABLE_DEFECT"
        severity = "Medium"
        error_code = "CABLE_DEFECT"

    elif error_code is not None:
        # OCPP har selv rapporteret en fejlkode
        detected_incident = "CONNECTOR_FAULT"
        severity = "Medium"

    # ---------- GEM TELEMETRI I DATABASEN ----------

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO telemetry_reading 
        (id, charger_id, power_kw, voltage, current_a, temperature, error_code) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (data["id"], data["charger_id"], power_kw, voltage, current_a, temperature, error_code)
    )
    conn.commit()

    # ---------- OPRET AUTOMATISK INCIDENT ----------
    # Opret kun incident hvis det IKKE er en grid-fejl
    # Grid-fejl er ikke VoltEdges ansvar

    incident_id = None
    if detected_incident and detected_incident != "GRID_OUTAGE":
        incident_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO incident 
            (id, charger_id, incident_type, severity, status) 
            VALUES (%s, %s, %s, %s, 'Open')""",
            (incident_id, data["charger_id"], detected_incident, severity)
        )
        conn.commit()

    cursor.close()
    conn.close()

    # ---------- RETURNER SVAR ----------

    return jsonify({
        "status": "ALARM" if detected_incident else "OK",
        "incident_type": detected_incident,
        "incident_id": incident_id,
        "severity": severity,
        "grid_status": grid_status,
        "readings": {
            "power_kw": power_kw,
            "voltage": voltage,
            "current_a": current_a,
            "temperature": temperature,
            "error_code": error_code
        }
    }), 201

# ---------- INCIDENTS API ----------

@app.route("/api/incidents", methods=["GET"])
def get_incidents():
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
    return jsonify(rows)

@app.route("/api/incidents/<string:incident_id>/resolve", methods=["PUT"])
def resolve_incident(incident_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM incident WHERE id = %s", (incident_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Incident not found"}), 404
    cursor.execute(
        "UPDATE incident SET status = 'Resolved', resolved_at = NOW() WHERE id = %s",
        (incident_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": f"Incident {incident_id} resolved"})

# ---------- TECHNICIAN ASSIGNMENTS API ----------

@app.route("/api/assignments", methods=["GET"])
def get_assignments():
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
    return jsonify(rows)

# ---------- ALERT NOTIFICATIONS API ----------

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
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
    return jsonify(rows)

# ---------- GRID STATUS API ----------

@app.route("/api/grid-status", methods=["GET"])
def get_grid_status():
    """
    Tjekker el-nettets status direkte fra Energinet
    Kan kaldes med ?area=DK1 eller ?area=DK2
    """
    area = request.args.get("area", "DK1")
    status = check_grid_status(area)
    return jsonify({
        "area": area,
        "grid_status": status,
        "description": {
            "GRID_OK": "El-nettet er stabilt",
            "GRID_STRESS": "El-nettet er under stress — mulig årsag til NO_POWER incidents",
            "GRID_UNKNOWN": "Kunne ikke hente data fra Energinet"
        }.get(status)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
    