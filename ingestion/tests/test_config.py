import pytest

from ingest.config import load_config

BASE_YAML = """
account: acct123
user: user123
role: role123
warehouse: wh123
database: db123
schema: schema123
"""


def test_loads_config_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(BASE_YAML + "password: not_secret_in_this_test\n")
    config = load_config(path)
    assert config.account == "acct123"
    assert config.password == "not_secret_in_this_test"


def test_env_var_overrides_yaml(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text(BASE_YAML + "password: from_yaml\n")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "from_env")
    config = load_config(path)
    assert config.password == "from_env"


def test_raises_when_required_field_missing(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("account: acct123\n")  # missing everything else
    with pytest.raises(ValueError, match="missing connection config"):
        load_config(path)
