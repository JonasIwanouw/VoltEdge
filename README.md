# VoltEdge Mobility A/S — Incident Management System

## Beskrivelse
VoltEdge er en automatiseret incident management løsning til styring og overvågning af EV-ladeinfrastruktur. Systemet detekterer automatisk fejl på ladestandere baseret på realtids telemetri, opretter incidents, kontakter teknikere og udfører root cause analyse — uden manuelle mellemled.

Løsningen er bygget med Domain Driven Design (DDD) og følger en modulær arkitektur med Flask, MySQL og Docker.

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

---

## Projektstruktur

```
VoltEdge/
  ├── .github/workflows/
  │     └── ci.yml                  ← GitHub Actions CI/CD pipeline
  ├── database/
  │     └── init.sql                ← Database schema
  ├── domain.py                     ← DDD: Value objects, entiteter og aggregate roots
  ├── app.py                        ← Flask API med alle endpoints
  ├── root_cause_analysis.py        ← Domain service: Root cause analyse
  ├── ml_service.py                 ← ML service: Predictive maintenance
  ├── generate_data.py              ← Script til generering af testdata
  ├── Dockerfile                    ← Container definition
  ├── docker-compose.yml            ← Multi-container setup
  ├── requirements.txt              ← Python pakker
  ├── .gitignore                    ← Ignorerer .env og seed.sql
  └── README.md
```

---

## DDD Domænemodel

Løsningen er implementeret efter Domain Driven Design med fire lag:

### Value Objects
Ingen identitet — defineres udelukkende af deres værdier:
- **Temperature** — temperaturmåling med `is_critical()` og `risk_level()`
- **Voltage** — spændingsmåling med `is_normal()` og `risk_level()`
- **Current** — strømstyrke med `is_flowing()`
- **Severity** — alvorlighed (Low/Medium/High/Critical)
- **IncidentType** — fejltype (OVER_TEMPERATURE/NO_POWER/CABLE_DEFECT)

### Entiteter
Har identitet — to entiteter med samme data er ikke ens:
- **TelemetryReading** — én telemetrimåling fra en ladestander
- **TechnicianAssignment** — teknikers tildeling til et incident
- **AlertNotification** — notifikation sendt til tekniker

### Aggregate Roots
Eneste indgang til aggregatet udefra:
- **Charger** — detekterer anomalier via `detect_anomaly()`
- **Incident** — håndterer livscyklus via `assign()`, `set_ongoing()`, `resolve()`

### Domain Services
Forretningslogik der går på tværs af aggregater:
- **root_cause_analysis.py** — analyserer telemetrihistorik og giver anbefalinger
- **ml_service.py** — predictive maintenance via Random Forest

### Domain Events (implicit flow)
```
AnomalyDetected → IncidentCreated → AssignmentCreated
→ NotificationCreated → AssignmentAccepted → IncidentAssigned
→ IncidentOngoing → IncidentResolved
```

---

## Incident Detection

Systemet detekterer automatisk tre fejltyper:

| Fejltype | Betingelse | Severity |
|---|---|---|
| `OVER_TEMPERATURE` | Temperatur > 80°C | Critical |
| `NO_POWER` | Voltage < 200V (og el-net OK) | High |
| `CABLE_DEFECT` | Current < 0.1A trods normal voltage | Medium |

Ved `NO_POWER` tjekkes Energinets live API for at skelne mellem intern fejl og ekstern strømafbrydelse.

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

**4. Generer testdata (1000 ladestandere, ~15.000 målinger):**
```bash
python3 generate_data.py
```

**5. Kør automatisk incident scanning:**
```bash
curl -X POST http://127.0.0.1:5000/api/scan-telemetry
```

**6. Udfyld root cause på alle incidents:**
```bash
curl -X POST http://127.0.0.1:5000/api/backfill-root-cause
```

---

## API Endpoints

| Method | URL | Beskrivelse |
|---|---|---|
| GET | `/ping` | Health check |
| GET | `/api/chargers` | Hent alle ladestandere |
| POST | `/api/telemetry` | Modtag telemetri og detekter fejl automatisk |
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

Løsningen testes via Postman med tre requests der simulerer det fulde flow:

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
{
    "accept": true
}
```

**3. TeknikerDummyApp — Løs incident (PUT /api/incidents/<id>/resolve)**

---

## ML — Predictive Maintenance

`ml_service.py` træner en Random Forest model på telemetri-data:

```bash
python3 ml_service.py
```

**Feature importance:**
- `current_a`: 38%
- `power_kw`: 27%
- `temperature`: 18%
- `voltage`: 16%

---

## CI/CD

GitHub Actions pipeline kører automatisk ved hvert push til `main`:
1. Starter MySQL testdatabase
2. Opretter tabeller via `init.sql`
3. Installerer Python pakker
4. Kører tests
5. Bygger Docker image

---

## Sikkerhed (DevSecOps)

- Passwords gemmes i `.env` — aldrig i kode eller GitHub
- `seed.sql` og `.env` er i `.gitignore`
- CI/CD bruger separate testpasswords
- Docker Compose overfører miljøvariable via environment-sektionen

---

## Forfattere
- Gruppe 8