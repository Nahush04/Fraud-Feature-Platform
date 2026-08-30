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

_(M1 Snowflake load-throughput numbers, and M3's real online-vs-cold-recompute
lookup benchmark against the actual IEEE-CIS feature history, land once the
trial account is set up and a real Databricks run has produced real
`feature_engineering` output to materialize.)_
