from fstore.offline import latest_per_entity, read_offline_features


def test_read_offline_features_from_real_delta_table(delta_path):
    df = read_offline_features(delta_path)
    assert len(df) == 5
    assert set(df["card1"]) == {100, 200}


def test_latest_per_entity_picks_max_transaction_dt(sample_features):
    latest = latest_per_entity(sample_features)
    latest_by_entity = dict(zip(latest["card1"], latest["TransactionID"]))
    assert latest_by_entity[100] == 3  # TransactionDT=5000, the max for entity 100
    assert latest_by_entity[200] == 5  # TransactionDT=9999, the max for entity 200
