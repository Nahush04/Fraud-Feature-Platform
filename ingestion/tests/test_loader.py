from pathlib import Path

from ingest.loader import load_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transactions.csv"


class FakeConn:
    """Stands in for a snowflake.connector.SnowflakeConnection in tests."""


def fake_write_pandas(conn, df, table_name):
    assert isinstance(conn, FakeConn)
    assert table_name == "RAW_TRANSACTION"
    assert list(df.columns) == [c.upper() for c in df.columns]
    return True, 1, len(df), None


def test_load_csv_reports_total_rows_and_uppercases_columns():
    result = load_csv(
        FakeConn(),
        FIXTURE,
        "RAW_TRANSACTION",
        chunk_size=2,
        write_pandas_fn=fake_write_pandas,
    )
    assert result.rows_loaded == 5  # 5 data rows in the fixture, across 3 chunks of size 2
    assert result.elapsed_seconds >= 0
    assert result.rows_per_second > 0


def test_load_csv_raises_on_write_pandas_failure():
    def failing_write_pandas(conn, df, table_name):
        return False, 0, 0, None

    try:
        load_csv(FakeConn(), FIXTURE, "RAW_TRANSACTION", write_pandas_fn=failing_write_pandas)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
