import pandas as pd
import pytest
from deltalake import write_deltalake


@pytest.fixture
def sample_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TransactionID": [1, 2, 3, 4, 5],
            "TransactionDT": [0, 1800, 5000, 100, 9999],
            "card1": [100, 100, 100, 200, 200],
            "entity_txn_count_1h": [0, 1, 1, 0, 1],
            "entity_amt_zscore": [None, None, 0.5, None, None],
        }
    )


@pytest.fixture
def delta_path(tmp_path, sample_features) -> str:
    path = str(tmp_path / "features_offline")
    write_deltalake(path, sample_features)
    return path
