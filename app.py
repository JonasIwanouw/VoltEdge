from flask import Flask, jsonify, request
import mysql.connector
import os
import uuid
import requests
from dotenv import load_dotenv
from root_cause_analysis import analyze_charger, get_mttr_stats, get_incident_stats

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

TEMP_THRESHOLD = 80.0
VOLTAGE_MIN = 200.0
CURRENT_MIN = 0.1

# ---------- ENERGINET GRID CHECK ----------

def check_grid_status(area="DK1"):
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
    required_fields = ["id", "charger_id", "power_kw", "voltage", "current_a", "temperature", "recorded_at" ]
    if not data or any(f not in data for f in required_fields):
        return jsonify({"error": f"Missing one of {required_fields}"}), 400

    power_kw    = data["power_kw"]
    voltage     = data["voltage"]
    current_a   = data["current_a"]
    temperature = data["temperature"]
    recorded_at = data["recorded_at"]
    error_code  = data.get("error_code", None)
    grid_status = None
    detected_incident = None
    severity = None

    if temperature > TEMP_THRESHOLD:
        detected_incident = "OVER_TEMPERATURE"
        severity = "Critical"
        error_code = "OVER_TEMPERATURE"
    elif voltage < VOLTAGE_MIN:
        grid_status = check_grid_status("DK1")
        if grid_status == "GRID_STRESS":
            detected_incident = "GRID_OUTAGE"
            severity = "High"
            error_code = "GRID_OUTAGE"
        else:
            detected_incident = "NO_POWER"
            severity = "High"
            error_code = "NO_POWER"
    elif current_a < CURRENT_MIN and voltage >= VOLTAGE_MIN:
        detected_incident = "CABLE_DEFECT"
        severity = "Medium"
        error_code = "CABLE_DEFECT"
    elif error_code is not None:
        detected_incident = "CONNECTOR_FAULT"
        severity = "Medium"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO telemetry_reading 
        (id, charger_id, power_kw, voltage, current_a, temperature, error_code, recorded_at) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (data["id"], data["charger_id"], power_kw, voltage, current_a, temperature, error_code, recorded_at)
    )
    conn.commit()

    incident_id = None
    if detected_incident and detected_incident != "GRID_OUTAGE":
        incident_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO incident 
            (id, charger_id, incident_type, severity, status) 
            VALUES (%s, %s, %s, %s, 'Open')""",
            (incident_id, data["charger_id"], detected_incident, severity)
        )
        notification_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO alert_notification
            (id, incident_id, channel, recipient, delivery_status)
            VALUES (%s, %s, %s, %s, %s)""",
            (notification_id, incident_id, "email", "tekniker@voltedge.dk", "Pending")
        )
        assignment_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO technician_assignment
            (id, incident_id, technician_id, confirmed)
            VALUES (%s, %s, %s, %s)""",
            (assignment_id, incident_id, "tech-001", False)
        )
        conn.commit()

    cursor.close()
    conn.close()

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

# ---------- TECHNICIAN RESPOND ----------

@app.route("/api/assignments/<string:assignment_id>/respond", methods=["PUT"])
def respond_assignment(assignment_id):
    data = request.get_json()
    if not data or "accept" not in data:
        return jsonify({"error": "Missing 'accept' field"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, incident_id FROM technician_assignment WHERE id = %s", (assignment_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Assignment not found"}), 404

    incident_id = row[1]

    if data["accept"]:
        cursor.execute(
            "UPDATE technician_assignment SET confirmed = TRUE WHERE id = %s",
            (assignment_id,)
        )
        cursor.execute(
            "UPDATE incident SET status = 'Assigned' WHERE id = %s",
            (incident_id,)
        )
        message = "Opgave accepteret — incident er nu Assigned"
    else:
        cursor.execute(
            "UPDATE technician_assignment SET confirmed = FALSE WHERE id = %s",
            (assignment_id,)
        )
        message = "Opgave afvist — incident forbliver Open"

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": message, "assignment_id": assignment_id})

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

# ---------- AUTOMATISK SCANNING AF TELEMETRI ----------

@app.route("/api/scan-telemetry", methods=["POST"])
def scan_telemetry():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.* FROM telemetry_reading t
        WHERE t.error_code IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM incident i 
            WHERE i.charger_id = t.charger_id
            AND i.incident_type = t.error_code
            AND i.status = 'Open'
        )
    """)
    readings = cursor.fetchall()

    severity_map = {
        "OVER_TEMPERATURE": "Critical",
        "NO_POWER": "High",
        "CABLE_DEFECT": "Medium",
        "CONNECTOR_FAULT": "Medium"
    }

    incidents_created = 0
    for reading in readings:
        incident_id = str(uuid.uuid4())
        severity = severity_map.get(reading["error_code"], "Low")
        cursor.execute(
            """INSERT INTO incident 
            (id, charger_id, incident_type, severity, status) 
            VALUES (%s, %s, %s, %s, 'Open')""",
            (incident_id, reading["charger_id"], reading["error_code"], severity)
        )
        notification_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO alert_notification
            (id, incident_id, channel, recipient, delivery_status)
            VALUES (%s, %s, %s, %s, %s)""",
            (notification_id, incident_id, "email", "tekniker@voltedge.dk", "Pending")
        )
        assignment_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO technician_assignment
            (id, incident_id, technician_id, confirmed)
            VALUES (%s, %s, %s, %s)""",
            (assignment_id, incident_id, "tech-001", False)
        )
        incidents_created += 1

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({
        "message": "Scanning færdig",
        "incidents_created": incidents_created
    })

# ---------- ROOT CAUSE ANALYSIS ----------

@app.route("/api/chargers/<string:charger_id>/root-cause", methods=["GET"])
def root_cause(charger_id):
    result = analyze_charger(charger_id)
    return jsonify(result)

@app.route("/api/stats/mttr", methods=["GET"])
def mttr_stats():
    return jsonify(get_mttr_stats())

@app.route("/api/stats/incidents", methods=["GET"])
def incident_stats():
    return jsonify(get_incident_stats())

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
