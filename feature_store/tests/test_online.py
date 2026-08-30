import fakeredis

from fstore.online import RedisOnlineStore, materialize


def make_store():
    return RedisOnlineStore(fakeredis.FakeStrictRedis())


def test_write_and_read_round_trip():
    store = make_store()
    store.write_vector(100, as_of=1800, features={"entity_txn_count_1h": 1, "entity_amt_zscore": 0.5})

    result = store.read_vector(100)
    assert result == {"as_of": 1800, "features": {"entity_txn_count_1h": 1, "entity_amt_zscore": 0.5}}


def test_read_missing_entity_returns_none():
    store = make_store()
    assert store.read_vector("does-not-exist") is None


def test_nan_features_serialize_to_null():
    store = make_store()
    store.write_vector(100, as_of=0, features={"entity_amt_zscore": float("nan")})
    result = store.read_vector(100)
    assert result["features"]["entity_amt_zscore"] is None


def test_materialize_writes_only_latest_row_per_entity(sample_features):
    store = make_store()
    written = materialize(sample_features, store)

    assert written == 2  # 2 distinct entities (card1: 100, 200)
    assert store.read_vector(100)["as_of"] == 5000
    assert store.read_vector(200)["as_of"] == 9999


def test_materialize_is_idempotent(sample_features):
    store = make_store()
    materialize(sample_features, store)
    first = store.read_vector(100)
    materialize(sample_features, store)
    second = store.read_vector(100)
    assert first == second
