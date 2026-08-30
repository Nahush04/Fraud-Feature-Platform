# fraud-feature-platform

A real-time fraud-scoring platform built around a proper feature store, on the
IEEE-CIS Fraud Detection dataset (~590K transactions, ~3.5% fraud).

**Status: M0-M3 built (ingestion CLI, Scala/Spark feature job, Python feature
store — all with passing test suites). M4 onward in progress. See
`docs/decisions.md` for what's real vs. planned at any point in time.**

## What this project is

One pipeline, seven pieces of evidence:

| Stage | Tech | Milestone |
|---|---|---|
| Raw ingestion | Python CLI → Snowflake | M1 |
| Feature engineering | Scala + Spark on Databricks → Delta Lake | M2 |
| Feature store (offline + online) | Python, Delta + Redis, point-in-time joins | M3 |
| Model training | XGBoost + MLflow, golden eval set | M4 |
| Real-time serving | Flask, Docker, Kubernetes (minikube), HPA | M5 |
| Analyst review app | Django + MySQL, audit trail | M6 |
| Integration | end-to-end demo across all of the above | M7 |

## Why a feature store (not just a training script)

The point of this project isn't "train an XGBoost model" — that's a few
lines. The point is the plumbing around it that a real fraud system needs:
features computed once in Spark and reused consistently at both training and
serving time, with an explicit point-in-time correctness guarantee (a
feature value used to score transaction T must only reflect data strictly
before T — see `feature_engineering/` and `feature_store/pit_join.py` for the
leakage tests that enforce this).

## Repo layout

```
ingestion/            Python CLI: IEEE-CIS CSVs -> Snowflake raw tables
feature_engineering/  Scala + sbt Spark job (Databricks): raw -> Delta feature tables
feature_store/        Python: offline reads, online (Redis) materialization, point-in-time joins
training/             XGBoost + MLflow training, baseline comparison, golden eval set
serving/              Flask real-time scoring API, containerized
infra/                Kubernetes manifests (minikube), docker-compose for local Redis/MySQL
load_testing/         Locust load tests, captured latency/scaling results
review_app/           Django + MySQL analyst review queue and audit trail
docs/                 architecture, benchmarks (generated, not hand-typed), decisions
data/                 dataset download instructions (not committed)
```

## Running it locally

Being filled in as each milestone lands. See `docs/decisions.md` for current
setup requirements (Snowflake trial, Databricks Community Edition, minikube,
Docker Compose).

## Benchmarks

All numbers in `docs/benchmarks.md` come from real runs, generated after the
component they describe is built — no placeholder numbers.
