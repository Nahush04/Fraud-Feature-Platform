from train.baseline import train_baseline
from train.data import select_feature_matrix, time_based_split
from train.evaluate import evaluate, format_comparison
from train.pipeline import train_xgboost


def test_evaluate_beats_no_skill_baseline_on_separable_synthetic_data(synthetic_frame):
    train_df, test_df = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)
    X_test, y_test = select_feature_matrix(test_df)

    model = train_xgboost(X_train, y_train)
    result = evaluate(model, X_test, y_test)

    no_skill_pr_auc = y_test.mean()  # PR-AUC of a random/constant classifier equals the positive rate
    assert result.pr_auc > no_skill_pr_auc * 2
    assert 0.5 <= result.roc_auc <= 1.0
    assert 0 <= result.f1_at_best_threshold <= 1


def test_evaluate_result_is_internally_consistent(synthetic_frame):
    train_df, test_df = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)
    X_test, y_test = select_feature_matrix(test_df)

    model = train_xgboost(X_train, y_train)
    result = evaluate(model, X_test, y_test)

    precision, recall = result.precision_at_best_threshold, result.recall_at_best_threshold
    if precision + recall > 0:
        expected_f1 = 2 * precision * recall / (precision + recall)
        assert result.f1_at_best_threshold == expected_f1


def test_format_comparison_includes_both_models_and_all_headline_metrics(synthetic_frame):
    train_df, test_df = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)
    X_test, y_test = select_feature_matrix(test_df)

    baseline_result = evaluate(train_baseline(X_train, y_train), X_test, y_test)
    xgb_result = evaluate(train_xgboost(X_train, y_train), X_test, y_test)

    report = format_comparison(baseline_result, xgb_result)

    assert "PR-AUC" in report
    assert "ROC-AUC" in report
    assert "baseline" in report.lower()
    assert "xgboost" in report.lower()
