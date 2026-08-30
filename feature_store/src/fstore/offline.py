"""Offline side of the feature store: read the Delta table `feature_engineering`
writes (see feature_engineering/src/main/scala/featureeng/FeatureEngineeringJob.scala).

Reads via `deltalake` (delta-rs) directly, not PySpark -- this component
never needs a JVM. The producer (Spark) and this reader only need to agree
on the Delta table format, not on a shared runtime.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from deltalake import DeltaTable

ENTITY_COL = "card1"
TIME_COL = "TransactionDT"
ID_COL = "TransactionID"


def read_offline_features(delta_path: str | Path) -> pd.DataFrame:
    table = DeltaTable(str(delta_path))
    df = table.to_pandas()
    return df.sort_values([ENTITY_COL, TIME_COL, ID_COL]).reset_index(drop=True)


def latest_per_entity(features: pd.DataFrame) -> pd.DataFrame:
    """The most recent feature row for each entity -- what the online store holds."""
    return (
        features.sort_values([ENTITY_COL, TIME_COL, ID_COL])
        .groupby(ENTITY_COL, as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )
