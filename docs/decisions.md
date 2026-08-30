# Decisions and tradeoffs

Honest record of choices made and their limits. Updated as each milestone
lands — nothing here is retrofitted to look cleaner than it was.

## M0 — environment

- **Snowflake trial (30-day) instead of a permanent paid account.** Fine for
  a portfolio build: the ingestion CLI and schema are what's being
  demonstrated, not a production Snowflake deployment. Trial expiry means
  the pipeline needs to be re-runnable against a fresh trial account without
  manual cleanup — ingestion is idempotent (truncate-and-load per run) for
  that reason.
- **Databricks Community Edition instead of a paid workspace.** Real
  limitations that shape M2: single-node cluster only (no true distributed
  execution — the Scala/Spark code is written to *scale* correctly, but the
  benchmark numbers reflect single-node timing, and that's stated plainly in
  `benchmarks.md`, not hidden), no Databricks Jobs scheduling (the feature
  job is run interactively via notebook or the Databricks CLI, not on a
  cron), no Unity Catalog (Delta tables live in the workspace's default
  catalog).
- **minikube instead of a managed Kubernetes cluster (EKS/GKE/AKS).** The
  Kubernetes evidence needed here is Deployment/Service/HPA/probe design and
  operational understanding, not cloud IAM plumbing. minikube demonstrates
  the same manifests and `kubectl` operations a managed cluster would use.
- **Redis (Docker Compose) instead of a managed online feature store
  (DynamoDB, Feast-managed, etc.).** Keeps the local build free and fast;
  the point-in-time-correctness and materialization logic in `feature_store/`
  is the actual evidence, and it's storage-backend-agnostic by design.

## M1 — ingestion

- **Schema inferred from a CSV sample instead of hand-written.** IEEE-CIS's
  `train_transaction.csv` has 434 columns, most of them anonymized `V1..V339`
  features — writing DDL by hand for every column would be pure busywork and
  a maintenance trap if the source data changes. `schema.py` samples the
  first N rows, classifies each column as INTEGER/FLOAT/VARCHAR, and widens
  a column's type the moment any sampled value doesn't fit the current
  guess. A small override map fixes the few columns worth naming explicitly
  (`isFraud` as BOOLEAN, `TransactionAmt` as FLOAT) rather than trusting the
  generic guess for everything.
- **`write_pandas` (PUT + COPY INTO) instead of row-by-row INSERT.** This is
  the standard Snowflake Python connector bulk-load path; chunking
  (default 50K rows) keeps memory bounded on the full ~590K-row file and
  gives a natural point to measure rows/sec.
- **Reconciliation is a separate command, not folded into `load`.** A load
  can succeed by its own accounting (`write_pandas` reports success) while
  still under- or over-counting rows if a chunk was silently skipped or a
  re-run wasn't truncated first — reconciliation checks the actual table,
  independently, after the fact.

## M2 — feature engineering on Databricks

- **`card1` as a proxy entity.** IEEE-CIS has no real customer/account ID.
  Public work on this dataset commonly uses `card1` (sometimes combined with
  more card/address fields) as a stand-in for "the same paying entity" —
  used here as-is, single-field, documented rather than dressed up as a real
  identifier.
- **RANGE frames with a single ORDER BY column for every count/mean/stddev
  feature.** Spark requires exactly one ORDER BY expression when a RANGE
  frame boundary is a numeric offset (as opposed to `UNBOUNDED`/`CURRENT
  ROW`). Ordering by `TransactionDT` alone means rows sharing the current
  row's exact timestamp have offset 0 and are excluded by the frame's `-1`
  upper bound regardless of physical row order — ties are handled correctly
  without needing a tiebreaker column, which only a RANGE frame gives you.
- **`entity_time_since_last_txn` is the one feature that isn't perfectly
  tie-safe.** It's built on `lag()` over a ROW frame (not RANGE, since `lag`
  needs a row position, not a value distance), ordered by
  `(TransactionDT, TransactionID)` for determinism. If two transactions for
  the same entity share an exact timestamp, this feature can report 0
  seconds since a same-timestamp "predecessor" rather than treating them as
  simultaneous. Documented rather than silently accepted; the dataset's
  effectively-continuous amounts make exact-timestamp collisions rare in
  practice, but it's a real limitation, not a hidden one.
- **Local test JVM needs explicit `--add-opens` flags (`build.sbt`,
  `Test / javaOptions`).** Only this machine's JDK 21/15 were available
  locally (no JDK 8/11); Spark 3.5 needs the classic reflective-access opens
  to run on Java 17+, which Databricks clusters set for you but a bare local
  JVM doesn't. Verified: `sbt test` passes (7 tests) against a real local
  Spark session, including the point-in-time leakage test.
- **`main()` isn't the real entry point.** Databricks Community Edition
  clusters don't accept submitted JARs and have no Jobs scheduling, so the
  job runs as `FeatureEngineeringJob.run(spark, config)` from a notebook
  cell. `main` exists to document the intended CLI shape and is what a paid
  workspace with Jobs would actually invoke via `spark-submit`.

(Further entries added as M3 onward land.)
