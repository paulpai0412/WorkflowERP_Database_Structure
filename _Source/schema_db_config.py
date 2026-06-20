# -*- coding: utf-8 -*-

from dataclasses import dataclass
import os


REQUIRED_ENV_VARS = (
    "WFERP_SCHEMA_DB_HOST",
    "WFERP_SCHEMA_DB_USERNAME",
    "WFERP_SCHEMA_DB_PASSWORD",
)


class SchemaDbConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SchemaDbConfig:
    host: str
    port: int
    database: str
    username: str
    password: str

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        missing = [name for name in REQUIRED_ENV_VARS if not env.get(name)]
        if missing:
            raise SchemaDbConfigError("Missing schema DB env vars: " + ", ".join(missing))

        try:
            port = int(env.get("WFERP_SCHEMA_DB_PORT", "1433"))
        except ValueError as exc:
            raise SchemaDbConfigError("WFERP_SCHEMA_DB_PORT must be an integer") from exc

        return cls(
            host=env["WFERP_SCHEMA_DB_HOST"],
            port=port,
            database=env.get("WFERP_SCHEMA_DB_DATABASE", "DSCSYS"),
            username=env["WFERP_SCHEMA_DB_USERNAME"],
            password=env["WFERP_SCHEMA_DB_PASSWORD"],
        )

    def redacted(self):
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": "***",
        }


def from_env(environ=None):
    return SchemaDbConfig.from_env(environ)
