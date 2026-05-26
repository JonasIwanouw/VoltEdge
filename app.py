# app.py
# VoltEdge Mobility A/S — Incident Management API
# Implementeret efter Domain Driven Design principper
#
# Bounded Contexts:
#   - Device Management   (device_management/)
#   - Incident Management (incident_management/)
#   - Notification        (notification/)

from flask import Flask, jsonify, request
import os
import uuid
import requests
from dotenv import load_dotenv

# ---------- DDD IMPORTS ----------
# Device Management
from device_management.charger import Charger, TelemetryReading
from device_management.charger_repository import ChargerRepository

# Incident Management
from incident_management.incident import Incident, IncidentType, Severity
from incident_management.technician_assignment import TechnicianAssignment
from incident_management.incident_repository import IncidentRepository, TechnicianAssignmentRepository

# Notification
from notification.alert_notification import AlertNotification
from notification.notification_repository import NotificationRepository

# Domain Services
from root_cause_analysis import analyze_charger, get_mttr_stats, get_incident_stats

# Domain Events
from events import (
    AnomalyDetected, IncidentCreated, AssignmentCreated,
    AssignmentAccepted, AssignmentRejected, IncidentResolved,
    IncidentOngoing, NotificationCreated
)

load_dotenv()

app = Flask(__name__)

# ---------- REPOSITORIES ----------
charger_repo = ChargerRepository()
incident_repo = IncidentRepository()
assignment_repo = TechnicianAssignmentRepository()
notification_repo = NotificationRepository()

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
    chargers = charger_repo.get_all()
    return jsonify([{
        "id": c.id,
        "location": c.location,
        "vendor": c.vendor,
        "model": c.model,
        "firmware": c.firmware,
        "status": c.status
    } for c in chargers])

@app.route("/api/chargers/<string:charger_id>", methods=["GET"])
def get_charger(charger_id):
    charger = charger_repo.get(charger_id)
    if not charger:
        return jsonify({"error": "Charger not found"}), 404
    return jsonify({
        "id": charger.id,
        "location": charger.location,
        "vendor": charger.vendor,
        "model": charger.model,
        "firmware": charger.firmware,
        "status": charger.status
    })

# ---------- TELEMETRI API ----------

@app.route("/api/telemetry", methods=["POST"])
def receive_telemetry():
    data = request.get_json()
    required_fields = ["id", "charger_id", "power_kw", "voltage",
                       "current_a", "temperature", "recorded_at"]
    if not data or any(f not in data for f in required_fields):
        return jsonify({"error": f"Missing one of {required_fields}"}), 400

    # ---------- DDD: Opret TelemetryReading entitet ----------
    try:
        reading = TelemetryReading(
            id=data["id"],
            charger_id=data["charger_id"],
            power_kw=data["power_kw"],
            voltage=data["voltage"],
            current_a=data["current_a"],
            temperature=data["temperature"],
            recorded_at=data["recorded_at"],
            error_code=data.get("error_code", None)
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # ---------- DDD: Hent Charger via repository ----------
    charger = charger_repo.get(data["charger_id"])
    if not charger:
        return jsonify({"error": "Charger not found"}), 404

    # ---------- DDD: Kald detect_anomaly på Charger aggregatet ----------
    grid_status = None
    if not reading.voltage.is_normal():
        grid_status = check_grid_status("DK1")

    incident_type_str, severity_str = charger.detect_anomaly(
        reading, grid_status or "GRID_OK"
    )

    # Opdater error_code
    error_code = incident_type_str if incident_type_str else data.get("error_code", None)
    reading.error_code = error_code

    # ---------- GEM TELEMETRI VIA REPOSITORY ----------
    charger_repo.save_telemetry(reading)

    # ---------- DDD: Opret Incident hvis anomali detekteret ----------
    incident_id = None
    if incident_type_str and incident_type_str != "GRID_OUTAGE":

        # Publiser AnomalyDetected event
        anomaly_event = AnomalyDetected(
            charger_id=charger.id,
            incident_type=incident_type_str,
            severity=severity_str,
            temperature=reading.temperature.celsius,
            voltage=reading.voltage.volts,
            current_a=reading.current_a.ampere
        )

        # Root cause analyse
        rca = analyze_charger(data["charger_id"])
        recommendation = rca.get("recommendation", None)

        # Opret Incident aggregate
        incident_id = str(uuid.uuid4())
        incident = Incident(
            id=incident_id,
            charger_id=charger.id,
            incident_type=IncidentType(incident_type_str),
            severity=Severity(severity_str),
            root_cause_recommendation=recommendation
        )
        incident_repo.save(incident)

        # Publiser IncidentCreated event
        incident_created_event = IncidentCreated(
            incident_id=incident.id,
            charger_id=incident.charger_id,
            incident_type=incident_type_str,
            severity=severity_str,
            root_cause_recommendation=recommendation
        )

        # Opret AlertNotification aggregate
        notification_id = str(uuid.uuid4())
        notification = AlertNotification(
            id=notification_id,
            incident_id=incident_id,
            channel="email",
            recipient="tekniker@voltedge.dk"
        )
        notification_repo.save(notification)

        # Publiser NotificationCreated event
        notification_event = NotificationCreated(
            notification_id=notification_id,
            incident_id=incident_id,
            channel="email",
            recipient="tekniker@voltedge.dk"
        )

        # Opret TechnicianAssignment aggregate
        assignment_id = str(uuid.uuid4())
        assignment = TechnicianAssignment(
            id=assignment_id,
            incident_id=incident_id,
            technician_id="tech-001"
        )
        assignment_repo.save(assignment)

        # Publiser AssignmentCreated event
        assignment_event = AssignmentCreated(
            assignment_id=assignment_id,
            incident_id=incident_id,
            technician_id="tech-001"
        )

    return jsonify({
        "status": "ALARM" if incident_type_str else "OK",
        "incident_type": incident_type_str,
        "incident_id": incident_id,
        "severity": severity_str,
        "grid_status": grid_status,
        "readings": {
            "power_kw": reading.power_kw,
            "voltage": reading.voltage.volts,
            "current_a": reading.current_a.ampere,
            "temperature": reading.temperature.celsius,
            "error_code": error_code
        }
    }), 201

# ---------- INCIDENTS API ----------

@app.route("/api/incidents", methods=["GET"])
def get_incidents():
    rows = incident_repo.get_all()
    return jsonify(rows)

@app.route("/api/incidents/<string:incident_id>/resolve", methods=["PUT"])
def resolve_incident(incident_id):
    incident = incident_repo.get(incident_id)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404

    try:
        incident.resolve()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    incident_repo.update_status(incident_id, "Resolved", resolved_at=True)

    # Publiser IncidentResolved event
    resolved_event = IncidentResolved(
        incident_id=incident_id,
        mttr_minutes=incident.mttr_minutes()
    )

    return jsonify({"message": f"Incident {incident_id} resolved"})

@app.route("/api/incidents/<string:incident_id>/ongoing", methods=["PUT"])
def update_incident_ongoing(incident_id):
    incident = incident_repo.get(incident_id)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404

    try:
        incident.set_ongoing()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    incident_repo.update_status(incident_id, "Ongoing")

    # Publiser IncidentOngoing event
    ongoing_event = IncidentOngoing(incident_id=incident_id)

    return jsonify({"message": f"Incident {incident_id} updated to Ongoing"})

# ---------- TECHNICIAN ASSIGNMENTS API ----------

@app.route("/api/assignments", methods=["GET"])
def get_assignments():
    rows = assignment_repo.get_all()
    return jsonify(rows)

@app.route("/api/assignments/<string:tech_id>", methods=["GET"])
def get_assignments_for_tech(tech_id):
    rows = assignment_repo.get_by_technician(tech_id)
    return jsonify(rows)

@app.route("/api/assignments/<string:assignment_id>/respond", methods=["PUT"])
def respond_assignment(assignment_id):
    data = request.get_json()
    if not data or "accept" not in data:
        return jsonify({"error": "Missing 'accept' field"}), 400

    assignment = assignment_repo.get(assignment_id)
    if not assignment:
        return jsonify({"error": "Assignment not found"}), 404

    if data["accept"]:
        assignment.accept()
        assignment_repo.update_confirmed(assignment_id, True)
        incident_repo.update_status(assignment.incident_id, "Assigned")

        # Publiser AssignmentAccepted event
        accepted_event = AssignmentAccepted(
            assignment_id=assignment_id,
            incident_id=assignment.incident_id,
            technician_id=assignment.technician_id
        )
        message = "Opgave accepteret — incident er nu Assigned"
    else:
        assignment.reject()
        assignment_repo.update_confirmed(assignment_id, False)

        # Publiser AssignmentRejected event
        rejected_event = AssignmentRejected(
            assignment_id=assignment_id,
            incident_id=assignment.incident_id,
            technician_id=assignment.technician_id
        )
        message = "Opgave afvist — incident forbliver Open"

    return jsonify({"message": message, "assignment_id": assignment_id})

# ---------- ALERT NOTIFICATIONS API ----------

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    rows = notification_repo.get_all()
    return jsonify(rows)

@app.route("/api/notifications/<string:incident_id>", methods=["GET"])
def get_notifications_for_incident(incident_id):
    rows = notification_repo.get_all()
    filtered = [r for r in rows if r["incident_id"] == incident_id]
    return jsonify(filtered)

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
    import mysql.connector
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
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
    cursor.close()
    conn.close()

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

        rca = analyze_charger(reading["charger_id"])
        recommendation = rca.get("recommendation", None)

        incident = Incident(
            id=incident_id,
            charger_id=reading["charger_id"],
            incident_type=IncidentType(reading["error_code"]),
            severity=Severity(severity),
            root_cause_recommendation=recommendation
        )
        incident_repo.save(incident)

        notification = AlertNotification(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            channel="email",
            recipient="tekniker@voltedge.dk"
        )
        notification_repo.save(notification)

        assignment = TechnicianAssignment(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            technician_id="tech-001"
        )
        assignment_repo.save(assignment)
        incidents_created += 1

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

# ---------- BACKFILL ROOT CAUSE ----------

@app.route("/api/backfill-root-cause", methods=["POST"])
def backfill_root_cause():
    incidents = incident_repo.get_without_root_cause()
    updated = 0
    for inc in incidents:
        rca = analyze_charger(inc["charger_id"])
        recommendation = rca.get("recommendation", None)
        if recommendation:
            incident_repo.update_root_cause(inc["id"], recommendation)
            updated += 1
    return jsonify({
        "message": "Backfill færdig",
        "incidents_updated": updated
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)