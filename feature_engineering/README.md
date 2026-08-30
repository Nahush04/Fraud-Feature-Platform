# feature_engineering

Scala + Spark job that turns raw IEEE-CIS transactions into point-in-time-safe
features, run on Databricks and writing to Delta Lake as the feature store's
offline table.

## Why point-in-time correctness is the whole point

A model trained on feature values that reflect the future looks great
offline and falls apart in production, because at serving time those future
values don't exist yet. Every feature here is built so a transaction's
feature value only reflects transactions strictly before it in time — see
the module doc on `Features.computeVelocityFeatures` and, especially,
`PointInTimeLeakageSpec`, which asserts a feature's value for an existing
transaction is unchanged whether or not a future transaction is later added
to the input.

## Features computed (per transaction, keyed by proxy entity `card1`)

| Feature | Meaning |
|---|---|
| `entity_txn_count_1h` / `entity_txn_count_24h` | count of the entity's transactions in the trailing 1h / 24h, current transaction excluded |
| `entity_prior_txn_count` | count of all of the entity's transactions strictly before this one |
| `entity_prior_amt_mean` / `entity_prior_amt_stddev` | running mean/stddev of the entity's prior transaction amounts |
| `entity_amt_zscore` | this transaction's amount, standardized against the entity's prior history; null until 2+ priors exist |
| `entity_time_since_last_txn` | seconds since the entity's previous transaction; null for the entity's first |
| `email_txn_count_24h` | trailing-24h count of transactions sharing this transaction's `P_emaildomain`; null when there's no email |

IEEE-CIS has no true customer/account ID, so `card1` stands in as a proxy
entity, following common practice for this dataset.

## Run tests

Needs a JDK (11/17/21 all work; Java 17+ needs the `--add-opens` flags
already set in `build.sbt`'s `Test / javaOptions`):

```bash
sbt test
```

7 tests, run against a real local Spark session (`local[2]`), not mocked —
correctness of the window-function logic is the thing being tested, and that
only means something if Spark actually executes it.

## Running against real data without a Databricks account yet

`LocalCsvFeatureJob` reads the real IEEE-CIS CSV directly on a local Spark
session and calls the exact same `Features.computeVelocityFeatures` that
`FeatureEngineeringJob` (the real Databricks entry point) calls — so the
feature logic is identical, only the source (local CSV vs. Snowflake) and
sink (Parquet vs. Delta) differ:

```bash
sbt "Test/runMain featureeng.LocalCsvFeatureJob ../data/raw/train_transaction.csv ../data/feature_engineering_output_parquet"
```

(Uses `Test/runMain` rather than `run` because Spark is a `Provided`
dependency, which sbt includes on the `Test` classpath but not the default
`Runtime` one.) On Windows, this also needs `winutils.exe`/`hadoop.dll` on
`HADOOP_HOME`/`PATH` — Spark's local filesystem writer shells out to Hadoop's
`Shell` utilities even for a plain local run. Real result on the full
590,540-row dataset: ~25 seconds, single-node (`docs/benchmarks.md`).

## Run on Databricks

Community Edition has no Jobs scheduling, so this runs interactively:

```scala
// in a Databricks notebook cell
import featureeng.FeatureEngineeringJob
val config = FeatureEngineeringJob.loadConfig("/dbfs/path/to/config.properties")
FeatureEngineeringJob.run(spark, config)
```

`config.properties` (not committed): `sfURL`, `sfUser`, `sfPassword`,
`sfDatabase`, `sfSchema`, `sfWarehouse`, `sfRole`, `transactionTable`,
`outputPath` (a DBFS or workspace path for the Delta output).

## Layout

```
src/main/scala/featureeng/
  Features.scala              pure DataFrame -> DataFrame feature logic (unit-testable, no I/O)
  FeatureEngineeringJob.scala  Snowflake read -> Features -> Delta write, run on Databricks
src/test/scala/featureeng/
  SparkSessionTestWrapper.scala  local[2] SparkSession fixture shared by the specs
  FeaturesSpec.scala              per-feature correctness
  PointInTimeLeakageSpec.scala    the leakage test described above
```
