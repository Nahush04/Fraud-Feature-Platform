"""Load the model artifact `training` produces (`fraud-train run --model-dir`)
and build the exact feature row the model was trained on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import xgboost as xgb


def load_model(model_dir: str | Path) -> tuple[xgb.XGBClassifier, dict]:
    model_dir = Path(model_dir)
    model = xgb.XGBClassifier()
    model.load_model(str(model_dir / "model.json"))
    meta = json.loads((model_dir / "meta.json").read_text())
    return model, meta


def build_feature_row(meta: dict, transaction_amt: float, online_vector: dict | None) -> pd.DataFrame:
    """One row in the exact FEATURE_COLUMNS order the model was trained on.

    `online_vector` is what `fstore.online.RedisOnlineStore.read_vector`
    returns (`{"as_of": ..., "features": {...}}`), or `None` for an entity
    the online store has never seen -- that's a legitimate state (a brand
    new card), not an error, and produces the same all-null feature row a
    genuinely-first transaction gets in training.
    """
    stored_features = online_vector["features"] if online_vector else {}

    row = {}
    for column in meta["feature_columns"]:
        if column == "TransactionAmt":
            row[column] = transaction_amt
        else:
            row[column] = stored_features.get(column)

    # A missing online feature deserializes from JSON as Python None, which
    # pandas keeps as `object` dtype in a single-row DataFrame rather than
    # NaN -- XGBoost rejects object-dtype columns outright (it can't tell a
    # missing numeric from a categorical). Casting to float64 turns every
    # None into a proper NaN, which XGBoost does handle natively.
    return pd.DataFrame([row], columns=meta["feature_columns"]).astype("float64")
