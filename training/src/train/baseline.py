"""Logistic regression baseline. XGBoost only earns its place in the story if
it's compared honestly against something simpler.
"""

from __future__ import annotations

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def train_baseline(X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    # median imputation because these features are legitimately missing
    # (e.g. a "first ever transaction" has no prior-history features), not
    # missing-at-random noise -- logistic regression can't take NaN directly
    # the way XGBoost can.
    pipeline = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("logreg", LogisticRegression(class_weight="balanced", max_iter=1000)),
        ]
    )
    pipeline.fit(X_train, y_train)
    return pipeline
