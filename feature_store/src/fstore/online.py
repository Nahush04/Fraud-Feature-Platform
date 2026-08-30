"""Online side of the feature store: the latest feature vector per entity,
materialized into Redis for low-latency lookups at serving time.

Takes any redis.Redis-shaped client (get/set), so tests can pass
`fakeredis.FakeStrictRedis()` instead of a live Redis instance.
"""

from __future__ import annotations

import json
import math
from typing import Any

import pandas as pd

from fstore.offline import ENTITY_COL, TIME_COL, latest_per_entity

KEY_PREFIX = "fstore:card1:"


def _key(entity_id: Any) -> str:
    return f"{KEY_PREFIX}{entity_id}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    return value


class RedisOnlineStore:
    def __init__(self, client):
        self._client = client

    def write_vector(self, entity_id: Any, as_of: int, features: dict) -> None:
        payload = {"as_of": as_of, "features": {k: _json_safe(v) for k, v in features.items()}}
        self._client.set(_key(entity_id), json.dumps(payload))

    def read_vector(self, entity_id: Any) -> dict | None:
        raw = self._client.get(_key(entity_id))
        if raw is None:
            return None
        return json.loads(raw)


def materialize(offline_features: pd.DataFrame, store: RedisOnlineStore) -> int:
    """Write the latest feature vector per entity into the online store.

    Idempotent: re-running against the same offline snapshot overwrites each
    entity's key with the same value, not append-and-drift.
    """
    latest = latest_per_entity(offline_features)
    feature_cols = [c for c in latest.columns if c not in (ENTITY_COL, TIME_COL)]

    # to_dict(orient="records") reads each column independently, so an
    # int-typed column stays int even when another column in the same row
    # holds NaN -- row-wise access (e.g. iterrows()) would upcast the whole
    # row to float and turn entity IDs like 100 into 100.0, silently
    # breaking every downstream key lookup.
    written = 0
    for row in latest.to_dict(orient="records"):
        entity_id = row[ENTITY_COL]
        as_of = row[TIME_COL]
        features = {c: row[c] for c in feature_cols}
        store.write_vector(entity_id, int(as_of), features)
        written += 1
    return written
