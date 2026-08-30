"""XGBoost training with MLflow tracking.

XGBoost handles NaN features natively (a missing prior-history feature is
routed by the learned split, not imputed), so unlike the baseline, X is
passed through unmodified.
"""

from __future__ import annotations

import pandas as pd
import xgboost as xgb

DEFAULT_PARAMS = {
    "n_estimators": 200,
    "max_depth": 5,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "eval_metric": "aucpr",
}


def _scale_pos_weight(y_train: pd.Series) -> float:
    positives = y_train.sum()
    negatives = len(y_train) - positives
    return negatives / positives if positives > 0 else 1.0


def train_xgboost(X_train: pd.DataFrame, y_train: pd.Series, params: dict | None = None) -> xgb.XGBClassifier:
    resolved_params = dict(DEFAULT_PARAMS)
    resolved_params.update(params or {})
    resolved_params.setdefault("scale_pos_weight", _scale_pos_weight(y_train))

    model = xgb.XGBClassifier(**resolved_params)
    model.fit(X_train, y_train)
    return model
