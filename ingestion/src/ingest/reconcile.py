"""Row-count reconciliation between the source CSV and the loaded Snowflake table.

Catches the two failure modes bulk loads actually have: a chunk silently
dropped (partial `write_pandas` failure that didn't raise) or a re-run that
duplicated rows into a table that wasn't truncated first.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReconcileResult:
    source_rows: int
    table_rows: int

    @property
    def matches(self) -> bool:
        return self.source_rows == self.table_rows


def count_csv_rows(csv_path: str | Path) -> int:
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # exclude header


def count_table_rows(conn, table: str) -> int:
    cursor = conn.cursor()
    try:
        cursor.execute(f'SELECT COUNT(*) FROM "{table.upper()}"')
        return cursor.fetchone()[0]
    finally:
        cursor.close()


def reconcile(conn, csv_path: str | Path, table: str) -> ReconcileResult:
    return ReconcileResult(
        source_rows=count_csv_rows(csv_path),
        table_rows=count_table_rows(conn, table),
    )
