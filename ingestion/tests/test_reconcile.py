from pathlib import Path

from ingest.reconcile import count_csv_rows, reconcile

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transactions.csv"


class FakeCursor:
    def __init__(self, count: int):
        self._count = count

    def execute(self, sql):
        assert "COUNT(*)" in sql
        return self

    def fetchone(self):
        return (self._count,)

    def close(self):
        pass


class FakeConn:
    def __init__(self, count: int):
        self._count = count

    def cursor(self):
        return FakeCursor(self._count)


def test_count_csv_rows_excludes_header():
    assert count_csv_rows(FIXTURE) == 5


def test_reconcile_matches_when_counts_equal():
    result = reconcile(FakeConn(5), FIXTURE, "RAW_TRANSACTION")
    assert result.source_rows == 5
    assert result.table_rows == 5
    assert result.matches


def test_reconcile_flags_mismatch():
    result = reconcile(FakeConn(3), FIXTURE, "RAW_TRANSACTION")
    assert not result.matches
