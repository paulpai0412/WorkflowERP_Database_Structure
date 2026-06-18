import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "_Source" / "schema_db_config.py"


def load_schema_db_config_module():
    spec = importlib.util.spec_from_file_location("schema_db_config_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_schema_db_config_reads_required_env():
    module = load_schema_db_config_module()

    config = module.SchemaDbConfig.from_env(
        {
            "WFERP_SCHEMA_DB_HOST": "db.example.com",
            "WFERP_SCHEMA_DB_PORT": "1500",
            "WFERP_SCHEMA_DB_DATABASE": "ERP_SYS",
            "WFERP_SCHEMA_DB_USERNAME": "schema_user",
            "WFERP_SCHEMA_DB_PASSWORD": "secret-password",
        }
    )

    assert config.host == "db.example.com"
    assert config.port == 1500
    assert config.database == "ERP_SYS"
    assert config.username == "schema_user"
    assert config.password == "secret-password"


def test_schema_db_config_defaults_port_and_database():
    module = load_schema_db_config_module()

    config = module.SchemaDbConfig.from_env(
        {
            "WFERP_SCHEMA_DB_HOST": "db.example.com",
            "WFERP_SCHEMA_DB_USERNAME": "schema_user",
            "WFERP_SCHEMA_DB_PASSWORD": "secret-password",
        }
    )

    assert config.port == 1433
    assert config.database == "DSCSYS"


@pytest.mark.parametrize(
    "missing_name",
    [
        "WFERP_SCHEMA_DB_HOST",
        "WFERP_SCHEMA_DB_USERNAME",
        "WFERP_SCHEMA_DB_PASSWORD",
    ],
)
def test_schema_db_config_rejects_missing_host_username_password(missing_name):
    module = load_schema_db_config_module()
    environ = {
        "WFERP_SCHEMA_DB_HOST": "db.example.com",
        "WFERP_SCHEMA_DB_USERNAME": "schema_user",
        "WFERP_SCHEMA_DB_PASSWORD": "secret-password",
    }
    environ.pop(missing_name)

    with pytest.raises(module.SchemaDbConfigError) as excinfo:
        module.SchemaDbConfig.from_env(environ)

    assert missing_name in str(excinfo.value)


def test_schema_db_config_redacts_password_for_logging():
    module = load_schema_db_config_module()

    config = module.SchemaDbConfig.from_env(
        {
            "WFERP_SCHEMA_DB_HOST": "db.example.com",
            "WFERP_SCHEMA_DB_USERNAME": "schema_user",
            "WFERP_SCHEMA_DB_PASSWORD": "secret-password",
        }
    )

    assert config.redacted() == {
        "host": "db.example.com",
        "port": 1433,
        "database": "DSCSYS",
        "username": "schema_user",
        "password": "***",
    }
