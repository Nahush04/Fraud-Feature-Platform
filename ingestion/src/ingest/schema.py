"""Infer a Snowflake CREATE TABLE schema from a CSV header + a sample of rows.

IEEE-CIS has 434 columns on the transaction table alone (most of them
anonymized `V1`..`V339` features) -- hand-listing every column's type isn't
worth it. Instead: sample the first N rows, classify each column as
INTEGER / FLOAT / VARCHAR, and let a small override map fix the handful of
columns where the generic guess is wrong (e.g. `isFraud` is a flag, not a
generic integer feature, but INTEGER covers it fine either way -- overrides
exist for columns that need a specific width or type, not for correctness).
"""

from __future__ import annotations

import csv
from pathlib import Path

# column -> Snowflake type, for columns where sampled-type inference would
# pick something technically fine but non-obvious to a reader of the DDL.
KNOWN_OVERRIDES: dict[str, str] = {
    "TransactionID": "INTEGER",
    "isFraud": "BOOLEAN",
    "TransactionDT": "INTEGER",
    "TransactionAmt": "FLOAT",
}


def _classify(value: str) -> str:
    if value == "":
        return "VARCHAR"
    try:
        int(value)
        return "INTEGER"
    except ValueError:
        pass
    try:
        float(value)
        return "FLOAT"
    except ValueError:
        return "VARCHAR"


_RANK = {"INTEGER": 0, "FLOAT": 1, "VARCHAR": 2}


def _widen(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


def infer_schema(csv_path: str | Path, sample_rows: int = 2000) -> dict[str, str]:
    """Return {column_name: SQL_TYPE}, sampling up to `sample_rows` data rows."""
    csv_path = Path(csv_path)
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        types = {col: "INTEGER" for col in columns}  # start narrow, widen as needed
        for i, row in enumerate(reader):
            if i >= sample_rows:
                break
            for col in columns:
                types[col] = _widen(types[col], _classify(row.get(col, "")))

    for col, sql_type in KNOWN_OVERRIDES.items():
        if col in types:
            types[col] = sql_type

    return types


def render_create_table_sql(table: str, schema: dict[str, str]) -> str:
    columns_sql = ",\n    ".join(f'"{col}" {sql_type}' for col, sql_type in schema.items())
    return f'CREATE TABLE IF NOT EXISTS "{table.upper()}" (\n    {columns_sql}\n)'
