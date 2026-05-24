# VoltEdge Smart Charging API

REST-microservice der beregner en **optimal ladeplan** for en elbil: hvornaar og
med hvor meget effekt der skal lades, saa maalet naas inden deadline, til lavest
mulige pris, uden at overskride ladestanderens og nettets belastningsgraenser.

Dette er kernen i VoltEdges "smart charging" - bygget som teknisk MVP til 6.2
semestereksamen (KEA).

## Filer

| Fil | Indhold |
|---|---|
| `domain.py` | DDD-byggeklodserne: value objects, `ChargingProfile` (entity), `ChargingPlan` (aggregate root), domain events, `ChargingPlanOptimizer` (domain service) |
| `database.py` | Gem/hent i MySQL (rå SQL) |
| `main.py` | FastAPI-endpoints |
| `init.sql` | Databaseskema (2 tabeller) |
| `test_app.py` | Tests af domaenelogikken |

## DDD i koden

| Byggeklods | Hvor |
|---|---|
| Aggregate root | `ChargingPlan` |
| Entity | `ChargingProfile` |
| Value objects | `TimeWindow`, `PowerLevel`, `ChargingTarget`, `LoadConstraint`, `PriceSignal` |
| Domain service | `ChargingPlanOptimizer` |
| Domain events | `ChargingPlanCreated`, `ChargingPlanCompleted` |

## API-endpoints

| Metode | Endpoint | Beskrivelse |
|---|---|---|
| POST | `/charging-plans` | Beregn en optimal ladeplan |
| GET | `/charging-plans` | Hent alle ladeplaner |
| GET | `/charging-plans/{id}` | Hent én ladeplan |
| POST | `/charging-plans/{id}/complete` | Afslut ladning |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI (auto-genereret) |

## Kør lokalt

```bash
docker compose up --build
# API:     http://localhost:8000
# Swagger: http://localhost:8000/docs
```

Kør tests:

```bash
pip install -r requirements-dev.txt
pytest -v
ruff check .
```

## Eksempel-request

```json
POST /charging-plans
{
  "session_id": "session-001",
  "target_energy_kwh": 40,
  "deadline": "2026-05-23T07:00:00",
  "window_start": "2026-05-22T18:00:00",
  "window_end": "2026-05-23T07:00:00",
  "charger_max_power_kw": 11,
  "site_load_limit_kw": 11,
  "prices": [
    {"start": "2026-05-22T18:00:00", "price_per_kwh": 3.0},
    {"start": "2026-05-23T00:00:00", "price_per_kwh": 0.5}
  ]
}
```

## Teknologi

Python / FastAPI, MySQL, Docker + docker-compose, GitHub Actions (CI/CD).

Se `GUIDE.md` for trin-for-trin opsaetning af GitHub, Azure VM og MySQL.
