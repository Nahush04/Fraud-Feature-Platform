import fakeredis

from fstore.benchmark import run_benchmark
from fstore.online import RedisOnlineStore, materialize


def test_run_benchmark_reports_positive_timings_for_a_known_entity(sample_features):
    store = RedisOnlineStore(fakeredis.FakeStrictRedis())
    materialize(sample_features, store)

    result = run_benchmark(sample_features, store, entity_id=100, iterations=10)

    assert result.online_seconds_per_lookup >= 0
    assert result.cold_recompute_seconds_per_lookup >= 0
