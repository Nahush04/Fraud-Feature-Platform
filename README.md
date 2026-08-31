# fraud-feature-platform

A real-time fraud-scoring platform built around a proper feature store, on
the real IEEE-CIS Fraud Detection dataset (590,540 transactions, 3.499%
fraud). Built as portfolio evidence for skills a prior gap analysis found
missing: **Kubernetes, Databricks, Snowflake, Scala, Flask, Django, MySQL**
— each backed here by real, tested code, not a toy demo.

**The full loop runs for real, end to end** — a transaction gets ingested,
featurized, scored by a trained model, flagged, routed to a human review
queue, decided by an analyst, and logged to an append-only audit trail —
verified by `scripts/end_to_end_demo.py` against two real running servers
over real HTTP, not just per-component unit tests. See `docs/decisions.md`
for the two disclosed, real infra gaps (no Snowflake/Databricks account, no
Docker/minikube/MySQL server on this dev machine) and exactly what stands in
for each.

## Architecture

```
IEEE-CIS CSVs (590,540 real transactions)
   |  ingestion/ (Python CLI, chunked Snowflake load)
   v
Snowflake (RAW_TRANSACTION, RAW_IDENTITY)
   |  Databricks reads via the Snowflake-Spark connector
   v
Databricks -- feature_engineering/ (Scala + Spark)
   - point-in-time-safe features: velocity, amount z-score, time-since-last-txn
   - writes Delta Lake: the feature store's offline table
   v
feature_store/ (Python)
   - materialization: offline Delta -> online Redis (latest vector per entity)
   - point-in-time join for training (pandas.merge_asof, strictly-before)
   v
training/ (XGBoost + MLflow)
   - walk-forward (time-sliced) golden holdout, logistic-regression baseline
   v
serving/ (Flask, Docker, Kubernetes/minikube)
   - /score: Redis feature fetch -> model inference -> score + latency breakdown
   - flagged? -> notifies review_app's ingest API
   v
review_app/ (Django + MySQL)
   - analyst queue, approve/reject, append-only audit trail
```

## Skill evidence

| Gap skill | Where |
|---|---|
| **Snowflake** | `ingestion/` — schema-inferred bulk load (`write_pandas`, chunked), row-count reconciliation |
| **Databricks** | `feature_engineering/` — Scala/Spark job, written for the Databricks runtime (see `docs/decisions.md` for the Community Edition constraints this accounts for) |
| **Scala** | `feature_engineering/` — point-in-time-safe feature engineering, ScalaTest suite including an explicit leakage proof |
| **Kubernetes** | `infra/k8s/` — Deployment, Service, HPA, readiness/liveness probes tuned to actually mean something (readiness checks Redis, liveness doesn't) |
| **Flask** | `serving/` — the real-time scoring API |
| **Django** | `review_app/` — analyst review queue, session auth, append-only audit trail enforced at the model layer |
| **MySQL** | `review_app/fraud_review/settings.py` — the real configured backend (via PyMySQL), sqlite substitution documented and justified |

## What makes this more than a training script

Training an XGBoost model is a few lines. The actual engineering here is the
plumbing that makes it trustworthy in production:

- **Point-in-time correctness, proven, not assumed.** Every feature is
  computed so a transaction's feature value can only reflect data strictly
  before it — enforced with Spark RANGE-frame windows
  (`feature_engineering/Features.scala`) and proven directly by
  `PointInTimeLeakageSpec`: a transaction's features are asserted identical
  whether or not a future transaction exists in the input.
- **A real feature store, not a cache.** `feature_store/` keeps offline
  (full-history, for training's point-in-time joins) and online (latest-only,
  fast, for serving) in sync from one source of truth — measured, not
  assumed: 29x lookup speedup over cold recompute on the real dataset.
- **Honest model evaluation.** A walk-forward (never-shuffled) holdout,
  PR-AUC as the primary metric (fraud is ~3.5% positive — accuracy would
  lie), and a disclosed, explained reason the absolute PR-AUC is modest
  (8 engineered features, not the dataset's full 434 raw columns) — see
  `docs/benchmarks.md`.
- **Real bugs, found and documented, not hidden.** A pandas dtype-upcasting
  bug that silently broke Redis key lookups; an XGBoost `object`-dtype
  rejection only a real trained model over real HTTP surfaced; an MLflow
  backend deprecation. Each is in `docs/decisions.md` with what caught it
  and how it was fixed.

## Repo layout

```
ingestion/            Python CLI: IEEE-CIS CSVs -> Snowflake raw tables
feature_engineering/  Scala + sbt Spark job (Databricks): raw -> Delta feature tables
feature_store/        Python: offline reads, online (Redis) materialization, point-in-time joins
training/             XGBoost + MLflow training, baseline comparison, golden eval set
serving/              Flask real-time scoring API, containerized
infra/                Kubernetes manifests (minikube), docker-compose for local Redis/MySQL
load_testing/         Locust load test for the serving API
review_app/           Django + MySQL analyst review queue and audit trail
scripts/              end_to_end_demo.py -- the real, rerunnable full-loop demo
docs/                 architecture, benchmarks (generated, not hand-typed), decisions
data/                 dataset download instructions (not committed)
model/                the real trained model artifact (small enough to commit)
```

## Running it locally

Each component has its own README with setup/run/test instructions
(`ingestion/README.md`, `feature_engineering/README.md`,
`feature_store/README.md`, `training/README.md`, `serving/README.md`,
`review_app/README.md`). The fastest way to see the whole thing work:

```bash
cd scripts
../serving/.venv/Scripts/python.exe end_to_end_demo.py
```

(needs `data/feature_engineering_output` and `model/` — see
`feature_engineering/README.md`'s `LocalCsvFeatureJob` section and
`training/README.md` if you're rebuilding from scratch).

## Benchmarks

Every number in `docs/benchmarks.md` comes from a real run against real
data (590,540 real IEEE-CIS transactions) — no placeholders, no synthetic
stand-ins left in as final numbers. Headlines:

- **Feature engineering**: 590,540 transactions, ~25s single-node.
- **Feature store**: 13,553 entities materialized in 1.55s; 29.4x faster
  online lookup vs. cold recompute.
- **Model**: XGBoost PR-AUC 0.149 vs. 0.047 baseline vs. 0.034 no-skill
  (modest and explained, not oversold — see `docs/benchmarks.md`).
- **Serving**: p50 75ms / p95 80ms / p99 82ms, single dev-server process
  (real k8s numbers pending Docker/minikube — `docs/decisions.md`).
- **End-to-end**: the full score → flag → review → decision → audit-trail
  loop, passing, over real HTTP (`scripts/end_to_end_demo.py`).
