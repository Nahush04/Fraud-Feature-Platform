"""Load the feature-engineering output and prepare it for training.

`feature_engineering`'s Delta output already carries `isFraud` through
unchanged from the raw transaction (it's a static label, not something that
needs point-in-time joining), and each row's engineered features were
already computed as of that exact transaction's timestamp. So the offline
feature table *is* the training frame directly -- no separate join step is
needed here. (`fstore.pit_join` exists for the different case of scoring or
labeling an event that isn't already a row in that table.)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

LABEL_COL = "isFraud"
TIME_COL = "TransactionDT"

FEATURE_COLUMNS = [
    "TransactionAmt",
    "entity_txn_count_1h",
    "entity_txn_count_24h",
    "entity_prior_txn_count",
    "entity_prior_amt_mean",
    "entity_prior_amt_stddev",
    "entity_amt_zscore",
    "entity_time_since_last_txn",
    "email_txn_count_24h",
]


def load_training_frame(delta_path: str | Path) -> pd.DataFrame:
    from fstore.offline import read_offline_features  # local import: only needed for real Delta reads

    return read_offline_features(delta_path)


def time_based_split(df: pd.DataFrame, test_fraction: float = 0.2, time_col: str = TIME_COL) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward split: train on the earlier `1 - test_fraction` of
    transactions by time, test on the later `test_fraction` -- never a random
    shuffle, since shuffling would let the model train on transactions that
    happen after some of its own test transactions.
    """
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")

    ordered = df.sort_values(time_col).reset_index(drop=True)
    split_at = int(len(ordered) * (1 - test_fraction))
    return ordered.iloc[:split_at].copy(), ordered.iloc[split_at:].copy()


def select_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """(X, y) -- X is the fixed FEATURE_COLUMNS set, y is the fraud label as int."""
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing expected feature columns: {missing}")

    X = df[FEATURE_COLUMNS].copy()
    y = df[LABEL_COL].astype(int)
    return X, y
