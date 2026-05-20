-- VoltEdge Mobility A/S
-- Incident Management Database
-- Oprettet: 2026

CREATE DATABASE IF NOT EXISTS voltedge;
USE voltedge;

-- Aggregate Root: Charger
CREATE TABLE IF NOT EXISTS charger (
    id CHAR(36) PRIMARY KEY,
    location VARCHAR(200),
    vendor VARCHAR(100),
    model VARCHAR(100),
    firmware VARCHAR(50),
    status VARCHAR(20),
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Entitet under Charger
CREATE TABLE IF NOT EXISTS connector (
    id CHAR(36) PRIMARY KEY,
    charger_id CHAR(36),
    connector_no INT,
    status VARCHAR(20),
    FOREIGN KEY (charger_id) REFERENCES charger(id)
);

-- Value Objects: telemetri målinger
CREATE TABLE IF NOT EXISTS telemetry_reading (
    id CHAR(36) PRIMARY KEY,
    charger_id CHAR(36),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    power_kw DECIMAL(8,2),
    voltage DECIMAL(8,2),
    current_a DECIMAL(8,2),
    temperature DECIMAL(5,2),
    error_code VARCHAR(50),
    FOREIGN KEY (charger_id) REFERENCES charger(id)
);

-- Aggregate Root: Incident
CREATE TABLE IF NOT EXISTS incident (
    id CHAR(36) PRIMARY KEY,
    charger_id CHAR(36),
    incident_type VARCHAR(50),
    severity VARCHAR(20),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    status VARCHAR(20),
    FOREIGN KEY (charger_id) REFERENCES charger(id)
);

-- Entitet under Incident
CREATE TABLE IF NOT EXISTS technician_assignment (
    id CHAR(36) PRIMARY KEY,
    incident_id CHAR(36),
    technician_id CHAR(36),
    proposed_slot TIMESTAMP NULL,
    confirmed BOOLEAN DEFAULT FALSE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incident(id)
);

-- Aggregate Root: AlertNotification
CREATE TABLE IF NOT EXISTS alert_notification (
    id CHAR(36) PRIMARY KEY,
    incident_id CHAR(36),
    channel VARCHAR(20),
    recipient VARCHAR(200),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_status VARCHAR(20),
    FOREIGN KEY (incident_id) REFERENCES incident(id)
);
