# tests/test_domain.py
# Unit tests for DDD domæneklasser
# Tester value objects, entiteter og aggregate roots isoleret

import pytest
from device_management.charger import Charger, TelemetryReading, Temperature, Voltage, Current
from incident_management.incident import Incident, IncidentType, Severity
from incident_management.technician_assignment import TechnicianAssignment
from notification.alert_notification import AlertNotification


# ==============================================================
# VALUE OBJECT TESTS
# ==============================================================

class TestTemperature:
    def test_critical_temperature(self):
        temp = Temperature(95.0)
        assert temp.is_critical() == True

    def test_normal_temperature(self):
        temp = Temperature(60.0)
        assert temp.is_critical() == False

    def test_boundary_temperature(self):
        temp = Temperature(80.0)
        assert temp.is_critical() == False

    def test_risk_level_high(self):
        temp = Temperature(75.0)
        assert temp.risk_level() == "HØJ"

    def test_risk_level_medium(self):
        temp = Temperature(60.0)
        assert temp.risk_level() == "MEDIUM"

    def test_risk_level_low(self):
        temp = Temperature(30.0)
        assert temp.risk_level() == "LAV"

    def test_invalid_temperature(self):
        with pytest.raises(ValueError):
            Temperature(500.0)


class TestVoltage:
    def test_normal_voltage(self):
        voltage = Voltage(230.0)
        assert voltage.is_normal() == True

    def test_low_voltage(self):
        voltage = Voltage(150.0)
        assert voltage.is_normal() == False

    def test_boundary_voltage(self):
        voltage = Voltage(200.0)
        assert voltage.is_normal() == True

    def test_risk_level_high(self):
        voltage = Voltage(170.0)
        assert voltage.risk_level() == "HØJ"


class TestCurrent:
    def test_current_flowing(self):
        current = Current(10.0)
        assert current.is_flowing() == True

    def test_current_not_flowing(self):
        current = Current(0.0)
        assert current.is_flowing() == False

    def test_boundary_current(self):
        current = Current(0.1)
        assert current.is_flowing() == True


class TestSeverity:
    def test_critical_severity(self):
        severity = Severity("Critical")
        assert severity.is_critical() == True

    def test_non_critical_severity(self):
        severity = Severity("High")
        assert severity.is_critical() == False

    def test_requires_immediate_action_high(self):
        severity = Severity("High")
        assert severity.requires_immediate_action() == True

    def test_requires_immediate_action_low(self):
        severity = Severity("Low")
        assert severity.requires_immediate_action() == False

    def test_invalid_severity(self):
        with pytest.raises(ValueError):
            Severity("Unknown")


class TestIncidentType:
    def test_valid_incident_type(self):
        incident_type = IncidentType("OVER_TEMPERATURE")
        assert incident_type.code == "OVER_TEMPERATURE"

    def test_grid_related(self):
        incident_type = IncidentType("GRID_OUTAGE")
        assert incident_type.is_grid_related() == True

    def test_not_grid_related(self):
        incident_type = IncidentType("NO_POWER")
        assert incident_type.is_grid_related() == False

    def test_invalid_incident_type(self):
        with pytest.raises(ValueError):
            IncidentType("UNKNOWN_ERROR")


# ==============================================================
# AGGREGATE ROOT TESTS
# ==============================================================

class TestCharger:
    def setup_method(self):
        self.charger = Charger(
            id="test-charger-001",
            location="København - Rådhuspladsen",
            vendor="ABB",
            model="Terra 54",
            firmware="1.2.3",
            status="available"
        )

    def test_detect_over_temperature(self):
        reading = TelemetryReading(
            id="test-reading-001",
            charger_id="test-charger-001",
            power_kw=0.0,
            voltage=230.0,
            current_a=0.0,
            temperature=95.0,
            recorded_at="2026-05-26 10:00:00"
        )
        incident_type, severity = self.charger.detect_anomaly(reading)
        assert incident_type == "OVER_TEMPERATURE"
        assert severity == "Critical"

    def test_detect_no_power(self):
        reading = TelemetryReading(
            id="test-reading-002",
            charger_id="test-charger-001",
            power_kw=0.0,
            voltage=150.0,
            current_a=0.0,
            temperature=25.0,
            recorded_at="2026-05-26 10:00:00"
        )
        incident_type, severity = self.charger.detect_anomaly(reading, "GRID_OK")
        assert incident_type == "NO_POWER"
        assert severity == "High"

    def test_detect_cable_defect(self):
        reading = TelemetryReading(
            id="test-reading-003",
            charger_id="test-charger-001",
            power_kw=0.0,
            voltage=230.0,
            current_a=0.0,
            temperature=25.0,
            recorded_at="2026-05-26 10:00:00"
        )
        incident_type, severity = self.charger.detect_anomaly(reading)
        assert incident_type == "CABLE_DEFECT"
        assert severity == "Medium"

    def test_detect_normal(self):
        reading = TelemetryReading(
            id="test-reading-004",
            charger_id="test-charger-001",
            power_kw=11.0,
            voltage=230.0,
            current_a=20.0,
            temperature=45.0,
            recorded_at="2026-05-26 10:00:00"
        )
        incident_type, severity = self.charger.detect_anomaly(reading)
        assert incident_type is None
        assert severity is None

    def test_detect_grid_outage(self):
        reading = TelemetryReading(
            id="test-reading-005",
            charger_id="test-charger-001",
            power_kw=0.0,
            voltage=150.0,
            current_a=0.0,
            temperature=25.0,
            recorded_at="2026-05-26 10:00:00"
        )
        incident_type, severity = self.charger.detect_anomaly(reading, "GRID_STRESS")
        assert incident_type == "GRID_OUTAGE"
        assert severity == "High"

    def test_is_available(self):
        assert self.charger.is_available() == True

    def test_is_not_faulted(self):
        assert self.charger.is_faulted() == False


class TestIncident:
    def setup_method(self):
        self.incident = Incident(
            id="test-incident-001",
            charger_id="test-charger-001",
            incident_type=IncidentType("OVER_TEMPERATURE"),
            severity=Severity("Critical")
        )

    def test_initial_status_open(self):
        assert self.incident.status == "Open"

    def test_assign(self):
        self.incident.assign()
        assert self.incident.status == "Assigned"

    def test_set_ongoing(self):
        self.incident.assign()
        self.incident.set_ongoing()
        assert self.incident.status == "Ongoing"

    def test_resolve(self):
        self.incident.assign()
        self.incident.resolve()
        assert self.incident.status == "Resolved"
        assert self.incident.resolved_at is not None

    def test_cannot_resolve_open_incident(self):
        with pytest.raises(ValueError):
            self.incident.resolve()

    def test_mttr_none_when_not_resolved(self):
        assert self.incident.mttr_minutes() is None

    def test_is_open(self):
        assert self.incident.is_open() == True

    def test_is_not_resolved(self):
        assert self.incident.is_resolved() == False


class TestTechnicianAssignment:
    def setup_method(self):
        self.assignment = TechnicianAssignment(
            id="test-assignment-001",
            incident_id="test-incident-001",
            technician_id="tech-001"
        )

    def test_initial_not_confirmed(self):
        assert self.assignment.confirmed == False

    def test_accept(self):
        self.assignment.accept()
        assert self.assignment.is_confirmed() == True

    def test_reject(self):
        self.assignment.reject()
        assert self.assignment.is_pending() == True


class TestAlertNotification:
    def setup_method(self):
        self.notification = AlertNotification(
            id="test-notification-001",
            incident_id="test-incident-001",
            channel="email",
            recipient="tekniker@voltedge.dk"
        )

    def test_initial_status_pending(self):
        assert self.notification.delivery_status == "Pending"

    def test_mark_delivered(self):
        self.notification.mark_delivered()
        assert self.notification.is_delivered() == True

    def test_mark_failed(self):
        self.notification.mark_failed()
        assert self.notification.delivery_status == "Failed"