import mlflow

from train.baseline import train_baseline
from train.data import select_feature_matrix, time_based_split
from train.evaluate import evaluate
from train.pipeline import train_xgboost
from train.tracking import run_tracked


def test_run_tracked_logs_params_metrics_and_returns_a_finished_run(tmp_path, synthetic_frame):
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")

    train_df, test_df = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)
    X_test, y_test = select_feature_matrix(test_df)

    model, run_id = run_tracked(
        "test-experiment",
        "xgboost-test-run",
        {"model": "xgboost", "n_estimators": 50},
        lambda X, y: train_xgboost(X, y, params={"n_estimators": 50}),
        X_train,
        y_train,
        eval_result=evaluate(train_xgboost(X_train, y_train, params={"n_estimators": 50}), X_test, y_test),
    )

    run = mlflow.get_run(run_id)
    assert run.info.status == "FINISHED"
    assert run.data.params["model"] == "xgboost"
    assert "pr_auc" in run.data.metrics
    assert model is not None


def test_run_tracked_works_without_an_eval_result(tmp_path, synthetic_frame):
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")

    train_df, _ = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)

    _, run_id = run_tracked("test-experiment", "baseline-test-run", {"model": "logreg"}, train_baseline, X_train, y_train)

    run = mlflow.get_run(run_id)
    assert run.info.status == "FINISHED"
    assert run.data.metrics == {}
