import json

import numpy as np
import pandas as pd
import xgboost as xgb

from serving.model import build_feature_row, load_model

META = {"feature_columns": ["TransactionAmt", "entity_txn_count_1h", "entity_amt_zscore"]}


def test_build_feature_row_uses_request_amount_and_stored_features():
    vector = {"as_of": 100, "features": {"entity_txn_count_1h": 3, "entity_amt_zscore": 1.2}}
    row = build_feature_row(META, transaction_amt=50.0, online_vector=vector)

    assert list(row.columns) == META["feature_columns"]
    assert row.iloc[0]["TransactionAmt"] == 50.0
    assert row.iloc[0]["entity_txn_count_1h"] == 3
    assert row.iloc[0]["entity_amt_zscore"] == 1.2


def test_build_feature_row_fills_nulls_for_unknown_entity():
    row = build_feature_row(META, transaction_amt=50.0, online_vector=None)

    assert row.iloc[0]["TransactionAmt"] == 50.0
    assert pd.isna(row.iloc[0]["entity_txn_count_1h"])
    assert pd.isna(row.iloc[0]["entity_amt_zscore"])


def test_build_feature_row_is_all_numeric_dtype_even_with_a_stored_null_feature():
    # a feature stored as JSON null (e.g. email_txn_count_24h with no email)
    # must not leave the column as `object` dtype -- XGBoost rejects that
    # outright, regardless of whether the *values* would otherwise be numeric.
    vector = {"as_of": 100, "features": {"entity_txn_count_1h": 3, "entity_amt_zscore": None}}
    row = build_feature_row(META, transaction_amt=50.0, online_vector=vector)

    assert all(dtype.kind == "f" for dtype in row.dtypes)
    assert pd.isna(row.iloc[0]["entity_amt_zscore"])


def test_load_model_round_trips_a_real_saved_xgboost_model(tmp_path):
    X = pd.DataFrame({"a": np.random.rand(20), "b": np.random.rand(20)})
    y = np.random.randint(0, 2, size=20)
    trained = xgb.XGBClassifier(n_estimators=5).fit(X, y)

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    trained.save_model(str(model_dir / "model.json"))
    (model_dir / "meta.json").write_text(json.dumps({"feature_columns": ["a", "b"], "decision_threshold": 0.5}))

    loaded_model, loaded_meta = load_model(model_dir)

    assert loaded_meta["feature_columns"] == ["a", "b"]
    np.testing.assert_allclose(loaded_model.predict_proba(X), trained.predict_proba(X))
