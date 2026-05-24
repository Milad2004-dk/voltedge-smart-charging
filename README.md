# VoltEdge Smart Charging API

REST-microservice der beregner en **optimal ladeplan** for en elbil: hvornår og med hvor meget effekt der skal lades, så målet nås inden deadline, til lavest mulige pris, uden at overskride ladestanderens og nettets belastningsgrænser.

Dette er kernen i VoltEdges "smart charging" — bygget som teknisk MVP til 6.2-semestereksamen (KEA).

## Hvad løsningen gør

Givet et energimål, et tidsvindue, ladestanderens og sitets effektgrænse samt elprisen time for time, finder optimeringsmotoren de billigste timer at lade i og lægger en plan, der rammer målet uden at overskride grænserne. En plan kan oprettes, hentes, justeres (ved nyt prissignal) og afsluttes.

## Tech stack

- Python + FastAPI (REST-API med automatisk Swagger-dokumentation)
- MySQL (rå `mysql.connector`)
- Docker + docker-compose (API og database som én samlet enhed)
- GitHub Actions (CI/CD) → Azure VM

## Filer

| Fil | Indhold |
|---|---|
| `domain.py` | DDD-byggeklodserne: value objects, `ChargingProfile` (entity), `ChargingPlan` (aggregate root), domain events, `ChargingPlanOptimizer` (domain service) |
| `database.py` | Gem/hent i MySQL (rå SQL) |
| `main.py` | FastAPI-endpoints |
| `init.sql` | Databaseskema (2 tabeller) |
| `test_app.py` | Tests af domænelogikken |
| `Dockerfile`, `docker-compose.yml` | Container-opsætning (API + database) |
| `.github/workflows/ci-cd.yml` | CI/CD: build, test og deploy |

## DDD i koden

| Byggeklods | Hvor |
|---|---|
| Aggregate root | `ChargingPlan` |
| Entity | `ChargingProfile` |
| Value objects | `TimeWindow`, `PowerLevel`, `ChargingTarget`, `LoadConstraint`, `PriceSignal` |
| Domain service | `ChargingPlanOptimizer` |
| Domain events | `ChargingPlanCreated`, `ChargingPlanAdjusted`, `ChargingPlanCompleted` |

## Kør lokalt

Kræver Docker Desktop.

Åbn derefter Swagger-dokumentationen på http://localhost:8000/docs

## API-endpoints

| Metode | Sti | Funktion |
|---|---|---|
| GET | `/health` | Sundhedstjek |
| GET | `/charging-plans` | Hent alle planer |
| POST | `/charging-plans` | Opret en plan (kører optimeringen) |
| GET | `/charging-plans/{plan_id}` | Hent én plan |
| POST | `/charging-plans/{plan_id}/adjust` | Genberegn planen ved nyt prissignal |
| POST | `/charging-plans/{plan_id}/complete` | Afslut en plan |

## Tests

Testene dækker domænelogikken og kræver ingen database.

## CI/CD og deployment

Ved hvert push og pull request til `main` kører GitHub Actions automatisk: build af Docker-image, `ruff` (lint), `pytest` og en database-smoketest. Ved push til `main` deployes løsningen automatisk til en Azure VM via SSH og startes med docker-compose.