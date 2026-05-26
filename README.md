# VoltEdge Mobility A/S — Incident Management System

## Beskrivelse
VoltEdge er en automatiseret incident management løsning til styring og overvågning af EV-ladeinfrastruktur. Systemet detekterer automatisk fejl på ladestandere baseret på realtids telemetri, opretter incidents, kontakter teknikere og udfører root cause analyse — uden manuelle mellemled.

Løsningen er bygget med Domain Driven Design (DDD) og opdelt i tre bounded contexts med repository pattern, eksplicitte domain events og fuldt testdækning.

---

## Tech Stack

| Komponent | Teknologi |
|---|---|
| Backend API | Python / Flask |
| Database | MySQL 8.0 |
| Container | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| ML | scikit-learn (Random Forest) |
| Ekstern integration | Energinet API (el-net status) |
| API test | Postman |
| Unit tests | pytest (44 tests) |

---

## Projektstruktur

```
VoltEdge/
  ├── .github/workflows/
  │     └── ci.yml                        ← GitHub Actions CI/CD pipeline
  │
  ├── device_management/                  ← Bounded Context: Device Management
  │     ├── __init__.py
  │     ├── charger.py                    ← Charger aggregate root + value objects
  │     └── charger_repository.py        ← Repository pattern for Charger
  │
  ├── incident_management/               ← Bounded Context: Incident Management
  │     ├── __init__.py
  │     ├── incident.py                  ← Incident aggregate root + value objects
  │     ├── technician_assignment.py     ← TechnicianAssignment aggregate root
  │     └── incident_repository.py      ← Repository pattern for Incident + Assignment
  │
  ├── notification/                      ← Bounded Context: Notification
  │     ├── __init__.py
  │     ├── alert_notification.py        ← AlertNotification aggregate root
  │     └── notification_repository.py  ← Repository pattern for Notification
  │
  ├── tests/
  │     ├── test_domain.py               ← 44 unit tests for DDD klasser
  │     └── test_api.py                  ← API integration tests
  │
  ├── database/
  │     └── init.sql                     ← Database schema
  │
  ├── events.py                          ← Eksplicitte domain events
  ├── root_cause_analysis.py             ← Domain service: Root cause analyse
  ├── ml_service.py                      ← ML service: Predictive maintenance
  ├── app.py                             ← Flask API — orkestrerer bounded contexts
  ├── generate_data.py                   ← Script til generering af testdata
  ├── Dockerfile                         ← Container definition
  ├── docker-compose.yml                 ← Multi-container setup
  ├── requirements.txt                   ← Python pakker
  └── .gitignore
```

---

## DDD Domænemodel

### Bounded Contexts

**Device Management** — alt der handler om ladestandere og telemetri:
- `Charger` (aggregate root) — detekterer anomalier via `detect_anomaly()`
- `TelemetryReading` (entitet) — én måling fra en ladestander
- Value objects: `Temperature`, `Voltage`, `Current`

**Incident Management** — alt der handler om fejlhændelser og teknikere:
- `Incident` (aggregate root) — livscyklus Open → Assigned → Ongoing → Resolved
- `TechnicianAssignment` (aggregate root) — accept/afvis logik
- Value objects: `Severity`, `IncidentType`

**Notification** — alt der handler om notifikationer:
- `AlertNotification` (aggregate root) — leveringsstatus

### Repository Pattern
Al databaseadgang går via repositories — API-laget skriver aldrig SQL direkte:
```python
# API bruger repository — ikke SQL direkte
charger = charger_repo.get(charger_id)
incident_repo.save(incident)
```

### Domain Events
Eksplicitte events i `events.py` dokumenterer hvad der sker i systemet:
```
AnomalyDetected → IncidentCreated → AssignmentCreated
→ NotificationCreated → AssignmentAccepted → IncidentAssigned
→ IncidentOngoing → IncidentResolved
```

---

## Incident Detection

| Fejltype | Betingelse | Severity |
|---|---|---|
| `OVER_TEMPERATURE` | Temperatur > 80°C | Critical |
| `NO_POWER` | Voltage < 200V (og el-net OK) | High |
| `CABLE_DEFECT` | Current < 0.1A trods normal voltage | Medium |
| `GRID_OUTAGE` | Voltage < 200V + Energinet GRID_STRESS | High |

---

## Kom i gang

### Krav
- Docker Desktop
- Python 3.11+

### Start løsningen

**1. Klon repo:**
```bash
git clone https://github.com/JonasIwanouw/VoltEdge.git
cd VoltEdge
```

**2. Opret .env fil:**
```
DB_HOST=db
DB_USER=root
DB_PASSWORD=ditpassword
DB_NAME=voltedge
```

**3. Start med Docker:**
```bash
docker compose up -d
```

**4. Generer testdata:**
```bash
python3 generate_data.py
```

**5. Kør automatisk incident scanning:**
```bash
curl -X POST http://127.0.0.1:5000/api/scan-telemetry
```

**6. Kør unit tests:**
```bash
python3 -m pytest tests/ -v
```

---

## API Endpoints

| Method | URL | Beskrivelse |
|---|---|---|
| GET | `/ping` | Health check |
| GET | `/api/chargers` | Hent alle ladestandere |
| POST | `/api/telemetry` | Modtag telemetri og detekter fejl |
| GET | `/api/incidents` | Hent alle incidents |
| PUT | `/api/incidents/<id>/resolve` | Løs et incident |
| PUT | `/api/incidents/<id>/ongoing` | Sæt incident til igangværende |
| GET | `/api/assignments` | Hent alle teknikertildelinger |
| GET | `/api/assignments/<tech_id>` | Hent opgaver for specifik tekniker |
| PUT | `/api/assignments/<id>/respond` | Tekniker accepterer/afviser opgave |
| GET | `/api/notifications` | Hent alle notifikationer |
| GET | `/api/grid-status` | Live el-net status fra Energinet |
| POST | `/api/scan-telemetry` | Scan telemetri og opret incidents automatisk |
| POST | `/api/backfill-root-cause` | Udfyld root cause på eksisterende incidents |
| GET | `/api/chargers/<id>/root-cause` | Root cause analyse for en ladestander |
| GET | `/api/stats/mttr` | MTTR statistik per incident type |
| GET | `/api/stats/incidents` | Incident statistik og fordeling |

---

## Test med Postman

Tre requests simulerer det fulde flow:

**1. ChargerDummyUnit — Send telemetri (POST /api/telemetry)**
```json
{
    "id": "uuid",
    "charger_id": "charger-uuid",
    "power_kw": 0.0,
    "voltage": 230.0,
    "current_a": 0.0,
    "temperature": 95.0,
    "recorded_at": "2026-05-26 10:00:00"
}
```

**2. TeknikerDummyApp — Accepter opgave (PUT /api/assignments/<id>/respond)**
```json
{ "accept": true }
```

**3. TeknikerDummyApp — Løs incident (PUT /api/incidents/<id>/resolve)**

---

## Unit Tests

44 tests dækker alle DDD klasser:

```bash
python3 -m pytest tests/test_domain.py -v
# 44 passed in 1.74s
```

Tests dækker value objects, aggregate roots og entiteter — herunder edge cases som at resolve et Open incident kaster en ValueError.

---

## ML — Predictive Maintenance

```bash
python3 ml_service.py
```

Random Forest model trænet på telemetri — feature importance:
- `current_a`: 38%
- `power_kw`: 27%
- `temperature`: 18%
- `voltage`: 16%

---

## CI/CD

GitHub Actions kører automatisk ved push til `main`:
1. Starter MySQL testdatabase
2. Opretter tabeller via `init.sql`
3. Installerer pakker
4. Kører 44 unit tests
5. Bygger Docker image (kun hvis tests passer)

---

## Sikkerhed (DevSecOps)

- Passwords i `.env` — aldrig i kode eller GitHub
- `seed.sql` og `.env` i `.gitignore`
- CI/CD bruger separate testpasswords
- Docker Compose overfører miljøvariable via environment

---

## Forfattere
- Gruppe 8