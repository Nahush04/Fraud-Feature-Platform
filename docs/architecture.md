# Architecture

```
IEEE-CIS CSVs
   |  ingestion/ (Python CLI, chunked COPY INTO)
   v
Snowflake (RAW_TRANSACTION, RAW_IDENTITY)
   |  Databricks reads via Snowflake-Spark connector
   v
Databricks Community Edition -- feature_engineering/ (Scala + Spark)
   - point-in-time-safe aggregations: card/email velocity, time-since-last-txn,
     amount z-score vs entity history
   - writes Delta Lake table: features_offline
   v
feature_store/ (Python)
   - materialization CLI: features_offline -> Redis (latest vector per entity)
   - pit_join.py: as-of joins for training (feature values as they existed
     just before each labeled event)
   v
training/ (Python: XGBoost + MLflow)
   - golden, time-sliced eval set (train on earlier txns, test on later)
   - baseline: logistic regression, reported alongside XGBoost, honestly
   v
serving/ (Flask, Docker, Kubernetes/minikube)
   - /score: Redis feature fetch -> model inference -> score + latency breakdown
   - Deployment + Service + HPA + readiness/liveness probes
   v
review_app/ (Django + MySQL)
   - flagged-transaction queue, analyst approve/reject, append-only audit trail
```

## Point-in-time correctness

The single most important correctness property in this system: a feature
value used to score transaction T must reflect only data strictly before T's
timestamp. This is enforced in two places:

1. `feature_engineering/` — Spark window functions use a strict `<` bound on
   timestamp, never `<=`. Tested directly: a synthetic entity's feature value
   at time T must be identical whether or not rows at T+1 exist in the input.
2. `feature_store/pit_join.py` — training-time feature retrieval joins each
   labeled event to the feature values *as they existed just before* that
   event, not the current (possibly retroactively updated) online value.

This is the standard reason feature stores exist over ad hoc joins: without
it, a model trained on "current" feature values silently leaks future
information and looks better offline than it will ever perform in
production.

(Diagrams and per-component detail added as each milestone lands.)
