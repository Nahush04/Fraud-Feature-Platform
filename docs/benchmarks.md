# Benchmarks

All numbers below come from real runs against real data. Nothing here is a
placeholder or an estimate — a row is added only after the run that produced
it, and the command used to produce it is included so it can be reproduced.

## M2 — feature_engineering (local test run)

`sbt test`, local[2] Spark session, JDK 21, 2026-08-30:

```
Total number of tests run: 7
Suites: completed 2, aborted 0
Tests: succeeded 7, failed 0, canceled 0, ignored 0, pending 0
Run completed in 15.5 seconds.
```

This is local[2] correctness verification, not a Databricks throughput
number — job runtime vs. real input row count on Databricks Community
Edition (single-node) gets added here once M2's real Databricks run happens.

## M2 — feature_engineering on the real IEEE-CIS dataset (local Spark, standing in for Databricks)

`sbt "Test/runMain featureeng.LocalCsvFeatureJob ../data/raw/train_transaction.csv ../data/feature_engineering_output_parquet"`,
`local[*]` Spark session, JDK 21, 2026-08-30, real `train_transaction.csv`
(no Snowflake/Databricks account exists yet — this reads the CSV directly and
writes Parquet instead of Delta; see `docs/decisions.md`):

```
rows=590540 elapsedSeconds=24.79
```

590,540 real transactions, all point-in-time-safe velocity/z-score/email
features computed, in ~25 seconds single-node. Real Databricks Community
Edition job-runtime numbers replace this once that workspace exists.

## M3 — feature store: online lookup vs. cold recompute, real IEEE-CIS data

`fstore benchmark` logic run directly against `data/feature_engineering_output`
(590,540 rows materialized into 13,553 distinct entities), 2026-08-30. Uses
`fakeredis` (in-process, no network round trip) rather than a real Redis
server — Docker isn't available on this machine, so this understates real
Redis's network latency; the online-vs-cold *shape* of the result is real,
the absolute online number would be somewhat higher against a real Redis
instance. Benchmarked entity `card1=7919`, the single busiest entity in the
dataset (14,932 transactions):

```
materialized 13553 entities in 1.55s from 590,540 rows
online lookup:  0.0718 ms/lookup
cold recompute: 2.1103 ms/lookup (entity has 14,932 rows)
speedup: 29.4x
```

Real Redis network-latency numbers replace this once Docker is available.

## M4 — model training on the real IEEE-CIS dataset

`fraud-train run --delta-path data/feature_engineering_output --test-fraction 0.2`,
2026-08-30. Walk-forward split: 472,432 train / 118,108 test transactions
(earliest 80% / latest 20% by `TransactionDT`), test-set fraud rate 3.441%:

```
metric                         baseline (logreg)        xgboost
PR-AUC                                    0.0467         0.1493
ROC-AUC                                   0.5985         0.7541
F1 @ best threshold                       0.1050         0.2266
best threshold                            0.5355         0.7490
```

XGBoost's PR-AUC (0.1493) is ~4.3x the no-skill baseline (the test set's
positive rate, 0.0344) and ~3.2x the logistic-regression baseline's PR-AUC.
These are modest absolute numbers by Kaggle-leaderboard standards — expected
and disclosed here rather than hidden, because `feature_engineering`
deliberately computes only 8 velocity/aggregation features from a handful of
raw columns (`TransactionAmt`, `card1`, `P_emaildomain`), not the dataset's
full 434-column raw feature set (`V1`..`V339`, `C1`..`C14`, `D1`..`D15`,
`M1`..`M9`, etc.) that leaderboard solutions engineer heavily against. The
point of this project is the feature-store/serving architecture around the
model, not maximizing this specific score — the comparison that matters here
is XGBoost vs. its own baseline on the same limited features, and it wins
clearly.

## M5 — real-time serving, single dev-server process (no k8s yet)

2026-08-30. Real trained model (`model/`) + real materialized IEEE-CIS data
(`fakeredis`, in-process — no real Redis, no Docker on this machine) behind
a real Werkzeug dev server (single process, no gunicorn workers), driven by
a real HTTP client (`requests`) with 8 concurrent threads, 100 requests,
`card1=7919` (the busiest real entity, 14,932 transactions):

```
statuses: {200}
p50=75.55ms p95=80.33ms p99=81.54ms max=81.57ms
```

Single request, no concurrency, same entity — from the raw `/score`
response's own `latency_ms` breakdown:

```
feature_fetch: 0.27-6.1 ms   inference: 10.6-33.2 ms   total: 10.9-39.4 ms
```

This is a single-process dev-server ceiling, not a production number — no
gunicorn worker pool, no k8s, no HPA, no real Redis network round trip. Real
multi-pod, HPA-scaled p50/p95/p99 and pod-count-over-time numbers (via
`load_testing/locustfile.py`) replace this once Docker/minikube are
available on a machine that has them.

## M6 — review_app (Django + MySQL)

`python manage.py test review`, sqlite (see `docs/decisions.md` for why),
2026-08-30:

```
Ran 15 tests in 8.7s
OK
```

Additionally verified against a real running dev server over real HTTP:
login (session cookie + CSRF), queue page (showed the real seeded flag),
detail page, approve action, and the resulting audit trail (`FLAGGED` then
`APPROVED`, correct analyst username) — all confirmed by inspecting the
actual HTML response, not asserted through Django's test client alone.

## M7 — end-to-end integration, real run

`scripts/end_to_end_demo.py`, 2026-08-30 — real Django server + real Flask
server, real trained model, real materialized IEEE-CIS data:

```
card1=5812 amount=50.0 model_score=0.8038 threshold=0.7490
/score response: flagged=True, notified_review_queue=True
found in queue as flag id 1
audit trail: FLAGGED then APPROVED, note "end-to-end demo"
clean teardown: no leftover processes, scratch db removed
END-TO-END DEMO PASSED
```

Note on how the (entity, amount) pair was chosen: not fabricated to force a
"flagged" outcome. An earlier manual attempt (`card1=7919`, a $4,999.99
transaction) scored 0.229 — well under threshold, given the model's modest
real PR-AUC (see M4). The script searches real materialized data for a
combination whose real score genuinely clears the real threshold, and the
demo's assertions would fail loudly if none existed among the top-50
busiest entities.

_(Real MySQL numbers land once Docker/a MySQL server is available. M1
Snowflake load-throughput numbers land once the Snowflake trial account is
set up.)_
