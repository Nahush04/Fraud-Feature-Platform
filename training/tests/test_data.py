import pytest

from train.data import select_feature_matrix, time_based_split


def test_time_based_split_never_lets_train_end_after_test_begins(synthetic_frame):
    train_df, test_df = time_based_split(synthetic_frame, test_fraction=0.2)

    assert len(train_df) + len(test_df) == len(synthetic_frame)
    assert train_df["TransactionDT"].max() <= test_df["TransactionDT"].min()


def test_time_based_split_respects_test_fraction(synthetic_frame):
    train_df, test_df = time_based_split(synthetic_frame, test_fraction=0.3)
    assert len(test_df) == pytest.approx(len(synthetic_frame) * 0.3, abs=1)


def test_time_based_split_rejects_invalid_fraction(synthetic_frame):
    with pytest.raises(ValueError):
        time_based_split(synthetic_frame, test_fraction=1.5)


def test_select_feature_matrix_returns_fixed_columns_and_int_label(synthetic_frame):
    X, y = select_feature_matrix(synthetic_frame)
    assert list(X.columns) == list(X.columns)  # FEATURE_COLUMNS order preserved
    assert y.dtype.kind in "iu"
    assert set(y.unique()) <= {0, 1}


def test_select_feature_matrix_raises_on_missing_columns(synthetic_frame):
    broken = synthetic_frame.drop(columns=["entity_amt_zscore"])
    with pytest.raises(ValueError, match="missing expected feature columns"):
        select_feature_matrix(broken)
