import numpy as np

from train.baseline import train_baseline
from train.data import select_feature_matrix, time_based_split
from train.pipeline import train_xgboost


def test_baseline_handles_nan_features_and_predicts_probabilities(synthetic_frame):
    train_df, test_df = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)
    X_test, y_test = select_feature_matrix(test_df)

    model = train_baseline(X_train, y_train)
    probs = model.predict_proba(X_test)[:, 1]

    assert probs.shape == (len(X_test),)
    assert np.all((probs >= 0) & (probs <= 1))


def test_xgboost_handles_nan_features_directly_and_predicts_probabilities(synthetic_frame):
    train_df, test_df = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)
    X_test, y_test = select_feature_matrix(test_df)

    assert X_train.isna().any().any()  # confirms this test actually exercises the NaN path

    model = train_xgboost(X_train, y_train)
    probs = model.predict_proba(X_test)[:, 1]

    assert probs.shape == (len(X_test),)
    assert np.all((probs >= 0) & (probs <= 1))


def test_xgboost_upweights_the_minority_class(synthetic_frame):
    train_df, _ = time_based_split(synthetic_frame)
    X_train, y_train = select_feature_matrix(train_df)

    model = train_xgboost(X_train, y_train)

    expected_ratio = (y_train == 0).sum() / (y_train == 1).sum()
    assert model.get_params()["scale_pos_weight"] == expected_ratio
