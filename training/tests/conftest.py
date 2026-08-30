import numpy as np
import pandas as pd
import pytest

from train.data import FEATURE_COLUMNS


def _synthetic_frame(n: int = 3000, fraud_rate: float = 0.05, seed: int = 0) -> pd.DataFrame:
    """A synthetic stand-in for feature_engineering's real output: sorted by
    time, imbalanced, with fraud rows nudged toward higher velocity/z-score
    features so the classifiers being tested have real signal to find.
    """
    rng = np.random.default_rng(seed)
    n_fraud = int(n * fraud_rate)
    is_fraud = np.zeros(n, dtype=int)
    is_fraud[rng.choice(n, size=n_fraud, replace=False)] = 1

    transaction_dt = np.sort(rng.integers(0, 30 * 86400, size=n))

    def signal(base_scale: float, fraud_shift: float) -> np.ndarray:
        return rng.normal(0, base_scale, size=n) + is_fraud * fraud_shift

    df = pd.DataFrame(
        {
            "TransactionID": np.arange(1, n + 1),
            "TransactionDT": transaction_dt,
            "isFraud": is_fraud,
            "TransactionAmt": np.clip(rng.normal(50, 20, size=n) + is_fraud * 40, 1, None),
            "entity_txn_count_1h": np.clip(rng.poisson(1, size=n) + is_fraud * rng.poisson(3, size=n), 0, None),
            "entity_txn_count_24h": np.clip(rng.poisson(3, size=n) + is_fraud * rng.poisson(5, size=n), 0, None),
            "entity_prior_txn_count": rng.poisson(5, size=n),
            "entity_prior_amt_mean": rng.normal(50, 10, size=n),
            "entity_prior_amt_stddev": np.abs(rng.normal(10, 3, size=n)),
            "entity_amt_zscore": signal(1.0, 3.0),
            "entity_time_since_last_txn": np.clip(rng.normal(3600, 1800, size=n) - is_fraud * 2000, 0, None),
            "email_txn_count_24h": np.clip(rng.poisson(1, size=n) + is_fraud * rng.poisson(2, size=n), 0, None),
        }
    )

    # sprinkle in the nulls a real "first transaction for this entity" would have
    null_mask = rng.random(n) < 0.05
    df.loc[null_mask, "entity_amt_zscore"] = np.nan
    df.loc[null_mask, "entity_time_since_last_txn"] = np.nan

    assert set(FEATURE_COLUMNS).issubset(df.columns)
    return df


@pytest.fixture
def synthetic_frame() -> pd.DataFrame:
    return _synthetic_frame()
