"""The "why does a feature store exist" number: online-store lookup latency
vs. recomputing an entity's latest feature vector cold from the full offline
history every time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd

from fstore.offline import ENTITY_COL, TIME_COL
from fstore.online import RedisOnlineStore


@dataclass(frozen=True)
class BenchmarkResult:
    online_seconds_per_lookup: float
    cold_recompute_seconds_per_lookup: float

    @property
    def speedup(self) -> float:
        return self.cold_recompute_seconds_per_lookup / self.online_seconds_per_lookup


def _cold_recompute(offline_features: pd.DataFrame, entity_id: Any) -> dict | None:
    entity_rows = offline_features[offline_features[ENTITY_COL] == entity_id]
    if entity_rows.empty:
        return None
    latest = entity_rows.sort_values(TIME_COL).iloc[-1]
    return latest.to_dict()


def run_benchmark(
    offline_features: pd.DataFrame,
    store: RedisOnlineStore,
    entity_id: Any,
    iterations: int = 200,
) -> BenchmarkResult:
    start = time.perf_counter()
    for _ in range(iterations):
        store.read_vector(entity_id)
    online_elapsed = (time.perf_counter() - start) / iterations

    start = time.perf_counter()
    for _ in range(iterations):
        _cold_recompute(offline_features, entity_id)
    cold_elapsed = (time.perf_counter() - start) / iterations

    return BenchmarkResult(
        online_seconds_per_lookup=online_elapsed,
        cold_recompute_seconds_per_lookup=cold_elapsed,
    )
