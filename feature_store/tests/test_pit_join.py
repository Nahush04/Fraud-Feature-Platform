import pandas as pd

from fstore.pit_join import point_in_time_join


def _history():
    return pd.DataFrame(
        {
            "TransactionID": [1, 2, 3],
            "TransactionDT": [0, 1000, 2000],
            "card1": [100, 100, 100],
            "entity_prior_txn_count": [0, 1, 2],
        }
    )


def test_event_gets_feature_row_strictly_before_it():
    events = pd.DataFrame({"event_id": ["e1"], "event_time": [1500], "card1": [100]})
    result = point_in_time_join(events, _history())

    # 1500 is between txn #2 (t=1000) and #3 (t=2000) -> as-of match is #2
    assert result.loc[0, "TransactionID"] == 2
    assert result.loc[0, "entity_prior_txn_count"] == 1


def test_event_at_exact_feature_timestamp_does_not_match_that_row():
    events = pd.DataFrame({"event_id": ["e1"], "event_time": [1000], "card1": [100]})
    result = point_in_time_join(events, _history())

    # event_time == txn #2's TransactionDT exactly -> must NOT match #2 (that would
    # be using a feature computed from data at the same instant as the label,
    # not strictly before it); must fall back to #1.
    assert result.loc[0, "TransactionID"] == 1


def test_event_before_any_history_gets_null_features():
    events = pd.DataFrame({"event_id": ["e1"], "event_time": [-1], "card1": [100]})
    result = point_in_time_join(events, _history())

    assert pd.isna(result.loc[0, "entity_prior_txn_count"])


def test_join_matches_within_entity_only():
    events = pd.DataFrame({"event_id": ["e1"], "event_time": [50000], "card1": [999]})
    result = point_in_time_join(events, _history())

    assert pd.isna(result.loc[0, "entity_prior_txn_count"])  # no history for entity 999


def test_adding_a_future_history_row_does_not_change_an_earlier_events_join():
    events = pd.DataFrame({"event_id": ["e1"], "event_time": [1500], "card1": [100]})

    before = point_in_time_join(events, _history())

    history_with_future_row = pd.concat(
        [_history(), pd.DataFrame({"TransactionID": [4], "TransactionDT": [3000], "card1": [100], "entity_prior_txn_count": [3]})],
        ignore_index=True,
    )
    after = point_in_time_join(events, history_with_future_row)

    assert before.loc[0, "entity_prior_txn_count"] == after.loc[0, "entity_prior_txn_count"]
