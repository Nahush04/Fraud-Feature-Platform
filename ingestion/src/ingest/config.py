"""Connection config: a YAML file for the non-secret bits (account, warehouse,
database, schema, role), environment variables for anything secret. This
keeps credentials out of the repo while the rest of the config stays
readable and diffable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_ENV_OVERRIDES = {
    "account": "SNOWFLAKE_ACCOUNT",
    "user": "SNOWFLAKE_USER",
    "password": "SNOWFLAKE_PASSWORD",
    "role": "SNOWFLAKE_ROLE",
    "warehouse": "SNOWFLAKE_WAREHOUSE",
    "database": "SNOWFLAKE_DATABASE",
    "schema": "SNOWFLAKE_SCHEMA",
}


@dataclass(frozen=True)
class ConnectionConfig:
    account: str
    user: str
    password: str
    role: str
    warehouse: str
    database: str
    schema: str

    def as_connect_kwargs(self) -> dict:
        return {
            "account": self.account,
            "user": self.user,
            "password": self.password,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
        }


def load_config(path: str | Path) -> ConnectionConfig:
    raw: dict = {}
    path = Path(path)
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    values = dict(raw)
    for field, env_var in _ENV_OVERRIDES.items():
        env_value = os.environ.get(env_var)
        if env_value:
            values[field] = env_value

    missing = [f for f in _ENV_OVERRIDES if not values.get(f)]
    if missing:
        raise ValueError(
            f"missing connection config: {', '.join(missing)} "
            f"(set in {path} or as env vars)"
        )

    return ConnectionConfig(**{f: values[f] for f in _ENV_OVERRIDES})
