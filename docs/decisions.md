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

## M3 — feature store

- **`deltalake` (delta-rs) instead of PySpark for reading the offline
  table.** This component never needs a JVM; the only contract between
  `feature_engineering` (Scala/Spark, writes Delta) and `feature_store`
  (Python, reads Delta) is the Delta table format itself.
- **Real bug caught by the test suite:** `materialize()` originally built
  each entity's feature dict with `DataFrame.iterrows()`. Because
  `entity_amt_zscore` is nullable (NaN for an entity's first two
  transactions), pandas silently upcasts the *entire row* — including the
  integer `card1` entity ID — to float when iterating row-wise, turning
  entity `100` into `100.0` and breaking every online-store key lookup for
  that entity. Fixed by switching to `DataFrame.to_dict(orient="records")`,
  which reads each column independently and keeps its own dtype. Caught by
  `test_materialize_writes_only_latest_row_per_entity` failing with a
  `NoneType` lookup miss, not by inspection — exactly the kind of
  cross-column-dtype bug a real feature store has to guard against.
- **The "cold recompute" benchmark comparator is pandas over the offline
  dataframe, not a live Databricks/Spark query.** This package has no Spark
  dependency, so `benchmark.py`'s cold path (filter + sort + take-last on
  the in-memory offline history) stands in for what a real cold path would
  cost — the online-vs-cold *shape* of the result is real, the absolute
  numbers understate what an actual Spark cluster query would cost, and
  that's stated here rather than presented as a Databricks number.
- **Point-in-time join via `pandas.merge_asof(..., allow_exact_matches=False)`,
  per entity via `by=`.** Chosen over a manual groupby+searchsorted
  implementation because merge_asof already does exactly this (as-of match,
  strictly-before via `allow_exact_matches=False`) and is the standard tool
  for it; tested directly for the same leakage property `feature_engineering`
  proves on the Spark side (`test_adding_a_future_history_row_does_not_change_an_earlier_events_join`).

## M4 — model training

- **The offline feature table doubles as the training frame directly.**
  `feature_engineering`'s Delta output carries `isFraud` through unchanged
  and each row's features are already computed as of that exact
  transaction's time, so no separate point-in-time join is needed to build
  a training set here — `fstore.pit_join` is for scoring/labeling an event
  that isn't already a row in the table (a different use case than training
  on the table itself).
- **Walk-forward (time-sliced) holdout, never a random split.** A random
  split would let the model train on transactions that happen after some of
  its own test transactions — something it will never see in production, so
  a model validated that way looks better offline than it will ever perform
  live. `time_based_split` sorts by `TransactionDT` and takes the earliest
  `1 - test_fraction` as train, matching the walk-forward discipline already
  used in the Stock-Prediction-with-GANs project.
- **PR-AUC as the primary metric, not accuracy or plain ROC-AUC.** Fraud is
  ~3.5% positive; a model that always predicts "not fraud" would still score
  ~96.5% accuracy and a deceptively fine-looking ROC-AUC. PR-AUC and a
  best-threshold F1 (tuned on the holdout's own precision-recall curve, not
  a fixed 0.5 cutoff) are reported instead, alongside ROC-AUC for context.
- **XGBoost gets raw NaN features; the logistic-regression baseline gets
  median-imputed ones.** A feature like `entity_amt_zscore` being null for
  an entity's first transaction is a real, meaningful state ("no prior
  history exists"), not noise to be imputed away — XGBoost can route missing
  values through a learned split, so it sees that state directly.
  Logistic regression has no such mechanism, so it gets `SimpleImputer`
  (median) ahead of scaling, which is a real, disclosed difference in how
  the two models see the same table, not an oversight.
- **Real bug caught here: MLflow's local filesystem tracking backend
  (`./mlruns`) is now in maintenance mode and raises by default** on a
  freshly installed `mlflow` (`MLFLOW_ALLOW_FILE_STORE` opt-out required).
  Found when the test suite failed immediately, not from reading MLflow's
  changelog. Fixed by defaulting to a local sqlite backend
  (`sqlite:///mlruns.db`) both in the CLI and in tests, only when the caller
  hasn't already pointed `MLFLOW_TRACKING_URI` somewhere real.
- **Tested against a synthetic, deliberately-imbalanced, deliberately-
  separable dataset (`tests/conftest.py`), not real IEEE-CIS data.** The
  real dataset was still downloading at the time this milestone was built;
  the synthetic generator exists so every test here exercises a real model
  fit and real metric computation (not mocks), and is a stand-in the same
  way `feature_engineering`'s local Spark tests stand in for a real
  Databricks run. Real IEEE-CIS numbers replace the synthetic ones in
  `docs/benchmarks.md` once the dataset and a real feature-engineering run
  exist.

## Real IEEE-CIS data lands (before M5)

- **Real dataset downloaded and validated**: 590,540 rows in
  `train_transaction.csv`, 3.499% fraud rate — matches expectations, via
  `data/download.py`.
- **No Snowflake or Databricks account exists yet**, so the real dataset
  couldn't go through the intended Snowflake → Databricks path. Rather than
  stay blocked, `feature_engineering/LocalCsvFeatureJob.scala` reads the CSV
  directly on a local Spark session and calls the exact same
  `Features.computeVelocityFeatures` function `FeatureEngineeringJob` (the
  real Databricks entry point) uses — so the feature logic being benchmarked
  is identical to what will run on Databricks, only the source/sink differ
  (local CSV → Parquet, instead of Snowflake → Delta). This produced a real
  590,540-row output in ~25 seconds single-node, real numbers in
  `docs/benchmarks.md` rather than synthetic ones.
- **Parquet, not Delta, from the local Spark run.** Delta wasn't wired into
  local `sbt run`/`sbt test` (no `delta-core` dependency, deliberately, since
  Databricks provides Delta at runtime and the JVM side never needed to
  write it locally before now). Converting Parquet to a real local Delta
  table via Python's `deltalake.write_deltalake` (already a `feature_store`
  dependency, already used in its own test fixtures) closed that gap without
  adding a JVM dependency just for a one-off local proof run.
  `data/feature_engineering_output` is now a real Delta table `feature_store`
  reads exactly the way it would read Databricks's real output.
- **M3's real benchmark used `fakeredis`, not a real Redis server** — Docker
  isn't installed on this machine. Disclosed directly in
  `docs/benchmarks.md`: the online-vs-cold-recompute *shape* is real (real
  590K-row dataset, real entity distribution), the absolute online-lookup
  number understates real Redis's network round-trip cost.
- **M4's real numbers are modest (XGBoost PR-AUC 0.149 vs. a 0.034 no-skill
  baseline) and that's disclosed, not smoothed over** — `feature_engineering`
  intentionally computes 8 velocity/aggregation features from a handful of
  raw columns, not the full 434-column raw feature set IEEE-CIS leaderboard
  solutions engineer against. The project's point is the feature-store and
  serving architecture, not chasing a leaderboard score; the fair comparison
  is XGBoost vs. the logistic-regression baseline on identical features, and
  XGBoost wins there by ~3.2x on PR-AUC.
- **Found a live bug via a real run, not synthetic tests**: `evaluate.py`'s
  `np.where` guard against dividing by a zero `precision + recall` still
  evaluated the division eagerly on every element (NumPy's `where`
  evaluates both branches), raising a `RuntimeWarning` on the real
  precision-recall curve's edge points. Fixed by dividing by a
  `np.where`-guarded denominator instead of the raw one.

## M5 — real-time serving on Kubernetes

- **`/healthz` never touches Redis or the model; `/readyz` does.** A k8s
  liveness probe failing means "kill and restart this pod" — that should
  never be triggered by a downstream dependency having a bad moment.
  Readiness failing just means "stop routing traffic here for now," which is
  the correct response to Redis being briefly unreachable.
- **`serving` depends on `feature_store` for `RedisOnlineStore` rather than
  re-implementing the Redis key/serialization scheme.** Both processes must
  agree on the exact key format and JSON shape; duplicating that logic would
  be a correctness risk (the two copies drifting) for no real benefit.
- **No Docker, minikube, or kubectl on this dev machine.** The Flask app,
  its model-loading/feature-building logic, and the full test suite are
  real and verified (including a real trained-model round trip and a real
  running HTTP server — see the bug below); the Dockerfile and k8s manifests
  are written and internally consistent but not yet built/deployed for
  real. That's a real gap, disclosed here and in `README.md`'s status line,
  not glossed over — deploying to an actual minikube cluster and running the
  Locust load test is the next real step once Docker is available.
- **Real bug found only by running a real HTTP request against a real
  trained model** (not caught by earlier unit tests, which used a stub
  model): `build_feature_row` left a missing online feature (JSON `null`)
  as Python `None` in the single-row DataFrame; pandas keeps that as
  `object` dtype rather than `NaN`, and XGBoost rejects `object`-dtype
  columns outright regardless of whether the underlying values are numeric.
  Fixed by casting the constructed row to `float64`; a regression test
  (`test_build_feature_row_is_all_numeric_dtype_even_with_a_stored_null_feature`)
  now covers it directly. This is exactly why the smoke test against a real
  server was worth doing even without a full k8s deploy — a stub model in
  unit tests can't catch a real XGBoost dtype constraint.
- **The trained model artifact (`model/model.json`, `model/meta.json`) is
  committed, not gitignored.** Unlike `mlruns.db` (regenerable local
  tracking state) or `data/raw` (large, license-gated dataset), this is a
  small (~750KB) real artifact the Docker image needs at build time — anyone
  cloning the repo can build and run `serving` without first re-running the
  full training pipeline.
- **Real (if partial) latency numbers exist despite no k8s**: a real
  Werkzeug dev server, loaded with the real trained model and real
  materialized IEEE-CIS data (via `fakeredis`, single process, no gunicorn
  workers, no k8s), answered real HTTP requests. Recorded in
  `docs/benchmarks.md` with that scope stated explicitly — single dev-server
  process latency, not a production/k8s number, and not the throughput a
  multi-pod HPA-scaled deployment would sustain.

## M6 — analyst review app (Django + MySQL)

- **MySQL is the configured default backend (via PyMySQL, not
  mysqlclient)** — PyMySQL is pure Python, so it installs without a C
  compiler or local MySQL client headers, which mysqlclient needs. No MySQL
  server is available on this dev machine, so `DJANGO_USE_SQLITE=true`
  (the default) swaps in sqlite for local dev and tests — the same kind of
  documented substitution as `fakeredis` for Redis and local Spark for
  Databricks elsewhere in this project. Every model, migration, and query is
  plain Django ORM, so nothing here is backend-specific; `docker compose up
  -d mysql` plus `DJANGO_USE_SQLITE=false` is the real path once available.
- **`AuditLogEntry.delete()` raises `NotImplementedError`, and the admin's
  `has_delete_permission` returns `False` for it too.** "Append-only by
  convention" isn't append-only — enforcing it at the model layer means a
  future view, script, or admin action can't silently violate the audit
  guarantee.
- **`services.py` (not `views.py`) owns the business logic** (`create_flag`,
  `decide_flag`), specifically so the M7 integration point — `serving/`'s
  Flask API writing a high-risk score into this queue — can call it
  directly (via a script or a small internal call) without going through
  HTTP or duplicating the flagging logic in a second place.
- **`decide_flag` refuses to act on an already-decided flag** (raises
  `ValueError` if not `PENDING`), tested directly
  (`test_deciding_twice_never_produces_a_third_audit_entry`) — a
  double-submitted approve/reject must not produce a second audit entry or
  silently no-op past the first decision.
- **Verified against a real running server, not just Django's test
  client**: started the real dev server, logged in over real HTTP
  (cookie-based session, CSRF token extracted and replayed), fetched the
  real queue page, approved a real seeded flag, and confirmed the audit
  trail showed both `FLAGGED` and `APPROVED` entries with the analyst's
  username attached — the same "run it for real, not just unit tests"
  discipline used for `serving/`'s smoke test.

(Further entries added as M7 onward land.)
