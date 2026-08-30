"""fstore: materialize offline (Delta) features into the online (Redis) store,
and benchmark online lookups against cold recomputation.

    fstore materialize --delta-path ../feature_engineering_output --redis-url redis://localhost:6379/0

    fstore benchmark --delta-path ../feature_engineering_output --redis-url redis://localhost:6379/0 --entity 100
"""

from __future__ import annotations

import argparse
import sys
import time

import redis

from fstore.benchmark import run_benchmark
from fstore.offline import read_offline_features
from fstore.online import RedisOnlineStore, materialize


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    mat_p = sub.add_parser("materialize", help="write the latest feature vector per entity into Redis")
    mat_p.add_argument("--delta-path", required=True)
    mat_p.add_argument("--redis-url", default="redis://localhost:6379/0")

    bench_p = sub.add_parser("benchmark", help="online lookup latency vs. cold recompute, for one entity")
    bench_p.add_argument("--delta-path", required=True)
    bench_p.add_argument("--redis-url", default="redis://localhost:6379/0")
    bench_p.add_argument("--entity", required=True)
    bench_p.add_argument("--iterations", type=int, default=200)

    return parser


def run(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    offline_features = read_offline_features(args.delta_path)
    client = redis.Redis.from_url(args.redis_url)
    store = RedisOnlineStore(client)

    if args.command == "materialize":
        start = time.perf_counter()
        count = materialize(offline_features, store)
        elapsed = time.perf_counter() - start
        print(f"materialized {count} entities in {elapsed:.2f}s")
        return 0

    if args.command == "benchmark":
        result = run_benchmark(offline_features, store, args.entity, iterations=args.iterations)
        print(f"online lookup:    {result.online_seconds_per_lookup * 1000:.4f} ms/lookup")
        print(f"cold recompute:   {result.cold_recompute_seconds_per_lookup * 1000:.4f} ms/lookup")
        print(f"speedup:          {result.speedup:.1f}x")
        return 0

    return 1


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
