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

(Further entries added as M2 onward land.)
