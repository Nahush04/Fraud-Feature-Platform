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

_(M1 Snowflake load-throughput numbers land once the Snowflake trial account
is set up.)_
