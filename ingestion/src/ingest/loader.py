"""Chunked CSV -> Snowflake load, timed for throughput benchmarking.

Uses `write_pandas`, which stages each chunk and issues `PUT` + `COPY INTO`
under the hood -- that's the standard bulk-load path for the Snowflake
Python connector, rather than row-by-row `INSERT`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

WritePandasFn = Callable[..., tuple[bool, int, int, Any]]


@dataclass(frozen=True)
class LoadResult:
    rows_loaded: int
    elapsed_seconds: float

    @property
    def rows_per_second(self) -> float:
        return self.rows_loaded / self.elapsed_seconds if self.elapsed_seconds > 0 else float("inf")


def load_csv(
    conn,
    csv_path: str | Path,
    table: str,
    chunk_size: int = 50_000,
    write_pandas_fn: WritePandasFn = write_pandas,
) -> LoadResult:
    csv_path = Path(csv_path)
    start = time.monotonic()
    rows_loaded = 0

    for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
        chunk.columns = [c.upper() for c in chunk.columns]
        success, _n_chunks, n_rows, _output = write_pandas_fn(conn, chunk, table.upper())
        if not success:
            raise RuntimeError(f"write_pandas reported failure loading into {table}")
        rows_loaded += n_rows

    elapsed = time.monotonic() - start
    return LoadResult(rows_loaded=rows_loaded, elapsed_seconds=elapsed)
