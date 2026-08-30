from pathlib import Path

from ingest.schema import infer_schema, render_create_table_sql

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transactions.csv"


def test_infers_expected_types():
    schema = infer_schema(FIXTURE)
    assert schema["TransactionID"] == "INTEGER"
    assert schema["isFraud"] == "BOOLEAN"  # override applied
    assert schema["TransactionAmt"] == "FLOAT"  # override + would've been widened anyway
    assert schema["ProductCD"] == "VARCHAR"  # letters -> can't be numeric
    assert schema["card4"] == "VARCHAR"


def test_widens_on_blank_values_without_forcing_varchar():
    schema = infer_schema(FIXTURE)
    # P_emaildomain has one blank row but is otherwise text -- blank alone
    # must not force VARCHAR via a different path than the text values do.
    assert schema["P_emaildomain"] == "VARCHAR"


def test_render_create_table_sql_quotes_columns_and_table():
    sql = render_create_table_sql("raw_transaction", {"TransactionID": "INTEGER", "isFraud": "BOOLEAN"})
    assert 'CREATE TABLE IF NOT EXISTS "RAW_TRANSACTION"' in sql
    assert '"TransactionID" INTEGER' in sql
    assert '"isFraud" BOOLEAN' in sql
