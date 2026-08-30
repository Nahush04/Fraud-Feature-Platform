"""fraud-ingest: load an IEEE-CIS CSV into a Snowflake raw table.

    fraud-ingest load --config config.yaml --file data/raw/train_transaction.csv \\
        --table RAW_TRANSACTION --create-table

    fraud-ingest reconcile --config config.yaml --file data/raw/train_transaction.csv \\
        --table RAW_TRANSACTION
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable

import snowflake.connector

from ingest.config import load_config
from ingest.loader import load_csv
from ingest.reconcile import reconcile
from ingest.schema import infer_schema, render_create_table_sql

ConnectFn = Callable[..., "snowflake.connector.SnowflakeConnection"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.yaml", help="path to connection config YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    load_p = sub.add_parser("load", help="load a CSV into a Snowflake table")
    load_p.add_argument("--file", required=True)
    load_p.add_argument("--table", required=True)
    load_p.add_argument("--chunk-size", type=int, default=50_000)
    load_p.add_argument("--create-table", action="store_true", help="infer schema and CREATE TABLE IF NOT EXISTS first")

    rec_p = sub.add_parser("reconcile", help="compare CSV row count to table row count")
    rec_p.add_argument("--file", required=True)
    rec_p.add_argument("--table", required=True)

    return parser


def run(argv: list[str], connect_fn: ConnectFn = snowflake.connector.connect) -> int:
    args = _build_parser().parse_args(argv)
    config = load_config(args.config)
    conn = connect_fn(**config.as_connect_kwargs())
    try:
        if args.command == "load":
            if args.create_table:
                schema = infer_schema(args.file)
                ddl = render_create_table_sql(args.table, schema)
                conn.cursor().execute(ddl)
                print(f"ensured table {args.table.upper()} ({len(schema)} columns)")

            result = load_csv(conn, args.file, args.table, chunk_size=args.chunk_size)
            print(
                f"loaded {result.rows_loaded:,} rows into {args.table.upper()} "
                f"in {result.elapsed_seconds:.1f}s ({result.rows_per_second:,.0f} rows/sec)"
            )
            return 0

        if args.command == "reconcile":
            result = reconcile(conn, args.file, args.table)
            status = "MATCH" if result.matches else "MISMATCH"
            print(f"{status}: source={result.source_rows:,} table={result.table_rows:,}")
            return 0 if result.matches else 1

        return 1
    finally:
        conn.close()


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
