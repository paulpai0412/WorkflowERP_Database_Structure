from skill_scripts.sqlite_readonly_adapter import translate_sqlserver_select_to_sqlite


def test_translates_any_database_bracketed_schema_identifiers():
    sql = "SELECT * FROM [VPIC1].[dbo].[ACPTA]"

    translated = translate_sqlserver_select_to_sqlite(sql)

    assert translated == 'SELECT * FROM "ACPTA"'
