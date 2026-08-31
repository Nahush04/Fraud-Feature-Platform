"""fraud-train: train the XGBoost model and a logistic-regression baseline on
a walk-forward holdout, tracked in MLflow, reported honestly side by side.

    fraud-train run --delta-path ../feature_engineering_output --test-fraction 0.2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import mlflow

from train.baseline import train_baseline
from train.data import FEATURE_COLUMNS, load_training_frame, select_feature_matrix, time_based_split
from train.evaluate import evaluate, format_comparison
from train.pipeline import train_xgboost
from train.tracking import run_tracked


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="train baseline + XGBoost, evaluate both on a time-sliced holdout")
    run_p.add_argument("--delta-path", required=True)
    run_p.add_argument("--test-fraction", type=float, default=0.2)
    run_p.add_argument("--experiment-name", default="fraud-detection")
    run_p.add_argument("--model-dir", help="if set, save the trained XGBoost model + serving metadata here")

    return parser


def run(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "run":
        return 1

    # mlflow's file-store backend ('./mlruns') is deprecated/maintenance-mode
    # as of mlflow 2.x -- default to a local sqlite store unless the caller
    # has already pointed MLFLOW_TRACKING_URI somewhere real.
    if "MLFLOW_TRACKING_URI" not in os.environ:
        mlflow.set_tracking_uri("sqlite:///mlruns.db")

    frame = load_training_frame(args.delta_path)
    train_df, test_df = time_based_split(frame, test_fraction=args.test_fraction)
    X_train, y_train = select_feature_matrix(train_df)
    X_test, y_test = select_feature_matrix(test_df)

    baseline_model, baseline_run_id = run_tracked(
        args.experiment_name, "logreg-baseline", {"model": "logistic_regression"}, train_baseline, X_train, y_train
    )
    baseline_eval = evaluate(baseline_model, X_test, y_test)

    xgb_model, xgb_run_id = run_tracked(
        args.experiment_name, "xgboost", {"model": "xgboost"}, train_xgboost, X_train, y_train
    )
    xgb_eval = evaluate(xgb_model, X_test, y_test)

    print(f"train rows: {len(train_df):,}  test rows: {len(test_df):,}  fraud rate (test): {y_test.mean():.3%}")
    print(f"MLflow runs: baseline={baseline_run_id} xgboost={xgb_run_id}")
    print()
    print(format_comparison(baseline_eval, xgb_eval))

    if args.model_dir:
        model_dir = Path(args.model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        xgb_model.save_model(str(model_dir / "model.json"))
        (model_dir / "meta.json").write_text(
            json.dumps(
                {
                    "feature_columns": FEATURE_COLUMNS,
                    "decision_threshold": float(xgb_eval.best_threshold),
                    "trained_on_rows": len(train_df),
                    "pr_auc": float(xgb_eval.pr_auc),
                    "mlflow_run_id": xgb_run_id,
                },
                indent=2,
            )
        )
        print(f"\nsaved model + metadata to {model_dir}")

    return 0


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
