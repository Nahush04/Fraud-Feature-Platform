from pathlib import Path

import ingest.cli as cli
from ingest.loader import LoadResult
from ingest.reconcile import ReconcileResult

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transactions.csv"

CONFIG_YAML = """
account: acct123
user: user123
password: pw123
role: role123
warehouse: wh123
database: db123
schema: schema123
"""


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def close(self):
        pass


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def _write_config(tmp_path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG_YAML)
    return path


def test_load_command_creates_table_then_loads(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    conn = FakeConn()

    monkeypatch.setattr(cli, "load_csv", lambda *a, **k: LoadResult(rows_loaded=5, elapsed_seconds=0.5))

    exit_code = cli.run(
        ["--config", str(config_path), "load", "--file", str(FIXTURE), "--table", "raw_transaction", "--create-table"],
        connect_fn=lambda **kwargs: conn,
    )

    assert exit_code == 0
    assert any("CREATE TABLE IF NOT EXISTS" in sql for sql in conn.cursor_obj.executed)
    assert conn.closed


def test_reconcile_command_returns_nonzero_on_mismatch(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    conn = FakeConn()

    monkeypatch.setattr(cli, "reconcile", lambda *a, **k: ReconcileResult(source_rows=5, table_rows=3))

    exit_code = cli.run(
        ["--config", str(config_path), "reconcile", "--file", str(FIXTURE), "--table", "raw_transaction"],
        connect_fn=lambda **kwargs: conn,
    )

    assert exit_code == 1
    assert conn.closed
