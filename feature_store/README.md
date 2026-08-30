# fstore

Python feature-store package: reads the Delta table `feature_engineering`
writes, materializes the latest feature vector per entity into Redis (the
online store), and joins historical feature values to training events
point-in-time-correctly.

## Why this exists as a separate layer

Training and serving need the *same* features computed the *same* way, but
they need them differently: training wants full history, joined as-of each
labeled event; serving wants "the latest vector for this entity, right now,
fast." Recomputing from the offline history on every request would work but
be slow (see `docs/benchmarks.md` for the online-vs-cold-recompute numbers);
serving on values that silently drift out of sync with the offline
definition would be worse. This package keeps both paths backed by one
source of truth (`feature_engineering`'s Delta output) instead.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Use

```bash
# start local Redis: docker compose -f ../infra/docker-compose.yml up -d redis

fstore materialize --delta-path ../feature_engineering_output --redis-url redis://localhost:6379/0
fstore benchmark   --delta-path ../feature_engineering_output --redis-url redis://localhost:6379/0 --entity 100
```

## Point-in-time join (for training)

```python
from fstore.offline import read_offline_features
from fstore.pit_join import point_in_time_join

history = read_offline_features("../feature_engineering_output")
training_events = ...  # columns: card1, event_time, isFraud
joined = point_in_time_join(training_events, history)
```

`point_in_time_join` uses `pandas.merge_asof(..., allow_exact_matches=False)`
per entity: for each event, the most recent feature row strictly before that
event's timestamp. `tests/test_pit_join.py` asserts this directly, including
that adding a future history row never changes an earlier event's join
result — the same leakage guarantee `feature_engineering`'s
`PointInTimeLeakageSpec` proves on the Spark side.

## Layout

```
src/fstore/
  offline.py     Delta table reads (deltalake / delta-rs, no JVM needed here)
  online.py      Redis-backed online store, JSON feature vectors, materialization
  pit_join.py    as-of join for training-time feature retrieval
  benchmark.py   online lookup vs. cold recompute-from-offline-history timing
  cli.py         fstore command-line entry point
tests/           pytest suite; fakeredis stands in for Redis, and Delta reads
                 are tested against a real local Delta table (written by the
                 test fixtures), not mocked
```

## Tests

```bash
pytest
```
