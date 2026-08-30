"""Evaluation on the walk-forward golden holdout: PR-AUC (primary, since fraud
is a rare-positive problem), ROC-AUC, and F1 at a threshold tuned on the
holdout's own precision-recall curve.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve, roc_auc_score


@dataclass(frozen=True)
class EvalResult:
    pr_auc: float
    roc_auc: float
    best_threshold: float
    f1_at_best_threshold: float
    precision_at_best_threshold: float
    recall_at_best_threshold: float


def _best_f1_threshold(y_true: pd.Series, scores: np.ndarray) -> tuple[float, float, float, float]:
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    # precision/recall have one more element than thresholds (the (1, 0) endpoint
    # with no threshold); drop it so every array lines up with a real threshold.
    precision, recall = precision[:-1], recall[:-1]
    denom = precision + recall
    # np.where evaluates both branches eagerly, so dividing by `denom`
    # directly would warn on the zero entries even though they're discarded;
    # divide by a safe placeholder there instead.
    f1_scores = np.where(denom > 0, 2 * precision * recall / np.where(denom > 0, denom, 1.0), 0.0)
    best_idx = int(np.argmax(f1_scores))
    return thresholds[best_idx], f1_scores[best_idx], precision[best_idx], recall[best_idx]


def evaluate(model, X_test: pd.DataFrame, y_test: pd.Series) -> EvalResult:
    scores = model.predict_proba(X_test)[:, 1]
    pr_auc = average_precision_score(y_test, scores)
    roc_auc = roc_auc_score(y_test, scores)
    best_threshold, f1, precision, recall = _best_f1_threshold(y_test, scores)

    return EvalResult(
        pr_auc=pr_auc,
        roc_auc=roc_auc,
        best_threshold=best_threshold,
        f1_at_best_threshold=f1,
        precision_at_best_threshold=precision,
        recall_at_best_threshold=recall,
    )


def format_comparison(baseline: EvalResult, xgboost: EvalResult) -> str:
    lines = [
        f"{'metric':<28}{'baseline (logreg)':>20}{'xgboost':>15}",
        f"{'PR-AUC':<28}{baseline.pr_auc:>20.4f}{xgboost.pr_auc:>15.4f}",
        f"{'ROC-AUC':<28}{baseline.roc_auc:>20.4f}{xgboost.roc_auc:>15.4f}",
        f"{'F1 @ best threshold':<28}{baseline.f1_at_best_threshold:>20.4f}{xgboost.f1_at_best_threshold:>15.4f}",
        f"{'best threshold':<28}{baseline.best_threshold:>20.4f}{xgboost.best_threshold:>15.4f}",
    ]
    return "\n".join(lines)
