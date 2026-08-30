# fraud-ingest

Config-driven CLI that loads the IEEE-CIS raw CSVs into Snowflake, with
schema inference (so 434-column `train_transaction.csv` doesn't need a
hand-written DDL) and row-count reconciliation.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Configure

```bash
cp config.example.yaml config.yaml   # gitignored
export SNOWFLAKE_PASSWORD=...        # never goes in the YAML file
```

## Use

```bash
# infer schema from the CSV header/sample, CREATE TABLE IF NOT EXISTS, then load
fraud-ingest --config config.yaml load \
    --file ../data/raw/train_transaction.csv --table RAW_TRANSACTION --create-table

fraud-ingest --config config.yaml load \
    --file ../data/raw/train_identity.csv --table RAW_IDENTITY --create-table

# verify row counts match the source CSV
fraud-ingest --config config.yaml reconcile \
    --file ../data/raw/train_transaction.csv --table RAW_TRANSACTION
```

## How the load works

`load` reads the CSV in chunks (`--chunk-size`, default 50,000 rows) and
calls `write_pandas` per chunk, which stages the chunk and runs
`PUT` + `COPY INTO` under the hood — the standard Snowflake bulk-load path,
not row-by-row `INSERT`. Throughput (rows/sec) is reported at the end and
recorded in `../docs/benchmarks.md` after a real run against the trial
account.

## Layout

```
src/ingest/
  config.py     YAML + env-var connection config (secrets never in the YAML)
  schema.py     column-type inference from a CSV sample, CREATE TABLE DDL
  loader.py     chunked write_pandas load, timed for throughput
  reconcile.py  source CSV row count vs loaded table row count
  cli.py        fraud-ingest command-line entry point
tests/          pytest suite; a fake connection/cursor stands in for
                Snowflake so tests run without a live account or credentials
```

## Tests

```bash
pytest
```
