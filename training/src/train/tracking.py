"""MLflow tracking wrapper. Local file-based tracking by default
(`./mlruns`) -- swapping in a real tracking server later is a URI change,
not a code change.
"""

from __future__ import annotations

from typing import Callable

import mlflow
import pandas as pd

from train.evaluate import EvalResult


def run_tracked(
    experiment_name: str,
    run_name: str,
    params: dict,
    train_fn: Callable[[pd.DataFrame, pd.Series], object],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    eval_result: EvalResult | None = None,
) -> tuple[object, str]:
    """Train `train_fn(X_train, y_train)`, logging params/metrics/model to MLflow.

    `eval_result` is computed by the caller (it needs the held-out test set,
    which this function doesn't take) and logged if provided.
    """
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(params)
        model = train_fn(X_train, y_train)

        if eval_result is not None:
            mlflow.log_metrics(
                {
                    "pr_auc": eval_result.pr_auc,
                    "roc_auc": eval_result.roc_auc,
                    "f1_at_best_threshold": eval_result.f1_at_best_threshold,
                    "best_threshold": eval_result.best_threshold,
                }
            )

        return model, run.info.run_id
