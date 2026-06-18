from dataclasses import replace

from skill_scripts.excel_intake import (
    DatabaseFieldRequirement,
    FormulaFieldRequirement,
    ReportFieldRequirement,
    WorkbookRequirement,
)
from skill_scripts.report_sql_builder import ReportSqlFilter, ReportSqlSort, build_report_select_sql


def _bundle():
    return {
        "modules": [{"ModuleID": "ACP", "ModuleName": "應付管理系統"}],
        "tables": [
            {"DB": "WFDB.dbo.", "TableID": "ACPTA", "TableName": "單頭", "ModuleID": "ACP"},
            {"DB": "WFDB.dbo.", "TableID": "ACPTB", "TableName": "單身", "ModuleID": "ACP"},
        ],
        "fields": [
            {"TableID": "ACPTA", "ID": "TA001", "FieldName": "單別"},
            {"TableID": "ACPTA", "ID": "TA002", "FieldName": "單號"},
            {"TableID": "ACPTA", "ID": "TA003", "FieldName": "日期"},
            {"TableID": "ACPTA", "ID": "TA018", "FieldName": "作廢"},
            {"TableID": "ACPTA", "ID": "TA024", "FieldName": "確認"},
            {"TableID": "ACPTB", "ID": "TB001", "FieldName": "單別"},
            {"TableID": "ACPTB", "ID": "TB002", "FieldName": "單號"},
            {"TableID": "ACPTB", "ID": "TB013", "FieldName": "科目"},
            {"TableID": "ACPTB", "ID": "TB014", "FieldName": "部門"},
            {"TableID": "ACPTB", "ID": "TB017", "FieldName": "未稅"},
            {"TableID": "ACPTB", "ID": "TB018", "FieldName": "稅額"},
        ],
        "index_keys": [
            {"TableName": "ACPTA", "IndexColumnName": "TA001+TA002", "isPrimaryKey": "1"},
            {"TableName": "ACPTB", "IndexColumnName": "TB001+TB002+TB003", "isPrimaryKey": "1"},
        ],
    }


def _requirement():
    return WorkbookRequirement(
        database_fields=[
            DatabaseFieldRequirement("ACPTA", "TA001", "單別"),
            DatabaseFieldRequirement("ACPTA", "TA002", "單號"),
            DatabaseFieldRequirement("ACPTA", "TA003", "日期"),
            DatabaseFieldRequirement("ACPTA", "TA018", "作廢"),
            DatabaseFieldRequirement("ACPTA", "TA024", "確認"),
            DatabaseFieldRequirement("ACPTB", "TB001", "單別"),
            DatabaseFieldRequirement("ACPTB", "TB002", "單號"),
            DatabaseFieldRequirement("ACPTB", "TB013", "科目"),
            DatabaseFieldRequirement("ACPTB", "TB014", "部門"),
            DatabaseFieldRequirement("ACPTB", "TB017", "未稅"),
            DatabaseFieldRequirement("ACPTB", "TB018", "稅額"),
        ],
        formula_fields=[FormulaFieldRequirement("總額", "=未稅+稅額")],
        report_fields=[
            ReportFieldRequirement("dept", "部門"),
            ReportFieldRequirement("account", "科目"),
            ReportFieldRequirement("untaxed", "", "=SUM(未稅)"),
            ReportFieldRequirement("tax", "", "=SUM(稅額)"),
            ReportFieldRequirement("total", "", "=SUM(總額)"),
            ReportFieldRequirement("total_pct", "", "=總額/SUM(總額)*100"),
        ],
        formula_lineage=[],
        warnings=[],
    )


def test_build_report_select_sql_uses_uploaded_fields_formulas_and_schema_relationships():
    sql = build_report_select_sql(
        "管理報表",
        _bundle(),
        _requirement(),
        filters=[
            ReportSqlFilter("日期", ">=", "20260101"),
            ReportSqlFilter("日期", "<=", "20260331"),
            ReportSqlFilter("作廢", "not_equals_or_blank", "Y"),
            ReportSqlFilter("確認", "=", "Y"),
        ],
        sorts=[ReportSqlSort("total", "DESC")],
    )

    assert "FROM [WFDB].[dbo].[ACPTA] header" in sql
    assert "JOIN [WFDB].[dbo].[ACPTB] detail" in sql
    assert "header.[TA001] = detail.[TB001]" in sql
    assert "detail.[TB014] AS dept" in sql
    assert "SUM(detail.[TB017]) AS untaxed" in sql
    assert "SUM(detail.[TB017] + detail.[TB018]) AS total" in sql
    assert "grand.grand_total_amount" in sql
    assert "ISNULL(header.[TA018], '') <> 'Y'" in sql
    assert "ORDER BY total DESC" in sql


def test_build_report_select_sql_fails_when_uploaded_field_is_not_in_schema():
    requirement = _requirement()
    requirement.database_fields[0] = replace(requirement.database_fields[0], field="BAD")

    try:
        build_report_select_sql("管理報表", _bundle(), requirement, filters=[])
        assert False, "expected schema validation failure"
    except ValueError as exc:
        assert str(exc) == "SCHEMA_FIELD_NOT_FOUND:ACPTA.BAD"


def test_build_report_select_sql_fails_without_relationship_for_multiple_tables():
    bundle = _bundle()
    bundle["index_keys"] = []

    try:
        build_report_select_sql("管理報表", bundle, _requirement(), filters=[])
        assert False, "expected relationship validation failure"
    except ValueError as exc:
        assert str(exc) == "SCHEMA_RELATIONSHIP_NOT_FOUND:ACPTA,ACPTB"
