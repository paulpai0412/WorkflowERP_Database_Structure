import pytest

from skill_scripts.postgres_readonly_adapter import (
    PostgresReadonlyAdapterError,
    translate_sqlserver_select_to_postgres,
)


def test_translates_bracketed_schema_identifiers():
    sql = "SELECT * FROM [DSCSYS].[dbo].[ACPTA]"

    translated = translate_sqlserver_select_to_postgres(sql)

    assert translated == 'SELECT * FROM dbo."ACPTA"'


def test_translates_any_database_bracketed_schema_identifiers():
    sql = "SELECT * FROM [VPIC1].[dbo].[ACPTA]"

    translated = translate_sqlserver_select_to_postgres(sql)

    assert translated == 'SELECT * FROM dbo."ACPTA"'


def test_translates_top_to_limit():
    sql = "SELECT TOP 20 * FROM [DSCSYS].[dbo].[ACPTA] ORDER BY TA003 DESC"

    translated = translate_sqlserver_select_to_postgres(sql)

    assert translated == 'SELECT * FROM dbo."ACPTA" ORDER BY "TA003" DESC LIMIT 20'


def test_translates_isnull_to_coalesce():
    sql = "SELECT * FROM [DSCSYS].[dbo].[ACPTA] WHERE ISNULL(TA018, '') <> 'Y'"

    translated = translate_sqlserver_select_to_postgres(sql)

    assert "COALESCE" in translated
    assert "ISNULL" not in translated
    assert '"TA018"' in translated


def test_preserves_readonly_select_semantics():
    sql = """
SELECT
    detail.TB014 AS expense_department,
    SUM(detail.TB017 + detail.TB018) AS total_amount
FROM [DSCSYS].[dbo].[ACPTA] header
JOIN [DSCSYS].[dbo].[ACPTB] detail
    ON header.TA001 = detail.TB001
WHERE header.TA003 >= '20260101'
GROUP BY detail.TB014
ORDER BY SUM(detail.TB017 + detail.TB018) DESC
"""

    translated = translate_sqlserver_select_to_postgres(sql)

    assert translated.lstrip().upper().startswith("SELECT")
    assert 'dbo."ACPTA" header' in translated
    assert 'detail."TB014" AS expense_department' in translated
    assert 'SUM(detail."TB017" + detail."TB018") AS total_amount' in translated


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO dbo.ACPTA VALUES ('X')",
        "UPDATE dbo.ACPTA SET TA024 = 'Y'",
        "DELETE FROM dbo.ACPTA",
        "DROP TABLE dbo.ACPTA",
        "ALTER TABLE dbo.ACPTA ADD x int",
        "EXEC dbo.proc",
        "MERGE dbo.ACPTA AS target USING dbo.ACPTB AS source ON 1 = 1",
        "TRUNCATE TABLE dbo.ACPTA",
        "CREATE TABLE dbo.bad(id int)",
        "GRANT SELECT ON dbo.ACPTA TO public",
        "REVOKE SELECT ON dbo.ACPTA FROM public",
    ],
)
def test_rejects_non_select_before_translation(sql):
    with pytest.raises(PostgresReadonlyAdapterError):
        translate_sqlserver_select_to_postgres(sql)


def test_rejects_semicolon_chained_statements():
    with pytest.raises(PostgresReadonlyAdapterError):
        translate_sqlserver_select_to_postgres(
            "SELECT * FROM [DSCSYS].[dbo].[ACPTA]; SELECT * FROM [DSCSYS].[dbo].[ACPTB]"
        )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM [DSCSYS].[dbo].[ACPTA] -- comment",
        "SELECT * FROM [DSCSYS].[dbo].[ACPTA] /* comment */",
    ],
)
def test_rejects_comments(sql):
    with pytest.raises(PostgresReadonlyAdapterError):
        translate_sqlserver_select_to_postgres(sql)


def test_rejects_sql_server_extended_procedures():
    with pytest.raises(PostgresReadonlyAdapterError):
        translate_sqlserver_select_to_postgres("SELECT * FROM xp_cmdshell")


def test_rejects_select_into_writes():
    with pytest.raises(PostgresReadonlyAdapterError):
        translate_sqlserver_select_to_postgres(
            "SELECT TA001 INTO dbo.copied_vouchers FROM [DSCSYS].[dbo].[ACPTA]"
        )
