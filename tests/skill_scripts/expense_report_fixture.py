from __future__ import annotations

from skill_scripts.excel_intake import (
    DatabaseFieldRequirement,
    FormulaFieldRequirement,
    ReportFieldRequirement,
    WorkbookRequirement,
)
from skill_scripts.report_sql_builder import ReportSqlFilter, ReportSqlSort, build_report_select_sql
from skill_scripts.schema_loader import load_schema_bundle


PROMPT = "請產出2026第一季費用分析，依部門與會計科目彙總未稅金額、稅額、總額與占比"


def expense_report_requirement() -> WorkbookRequirement:
    return WorkbookRequirement(
        database_fields=[
            DatabaseFieldRequirement("ACPTA", "TA001", "單別"),
            DatabaseFieldRequirement("ACPTA", "TA002", "單號"),
            DatabaseFieldRequirement("ACPTA", "TA003", "單據日期"),
            DatabaseFieldRequirement("ACPTA", "TA018", "作廢碼"),
            DatabaseFieldRequirement("ACPTA", "TA024", "確認碼"),
            DatabaseFieldRequirement("ACPTB", "TB001", "單別"),
            DatabaseFieldRequirement("ACPTB", "TB002", "單號"),
            DatabaseFieldRequirement("ACPTB", "TB013", "會計科目"),
            DatabaseFieldRequirement("ACPTB", "TB014", "費用部門"),
            DatabaseFieldRequirement("ACPTB", "TB017", "未稅金額"),
            DatabaseFieldRequirement("ACPTB", "TB018", "稅額"),
        ],
        formula_fields=[
            FormulaFieldRequirement("總額", "=未稅金額+稅額", "含稅總額"),
        ],
        report_fields=[
            ReportFieldRequirement("expense_department", "費用部門"),
            ReportFieldRequirement("expense_account", "會計科目"),
            ReportFieldRequirement("untaxed_amount", "", "=SUM(未稅金額)"),
            ReportFieldRequirement("tax_amount", "", "=SUM(稅額)"),
            ReportFieldRequirement("total_amount", "", "=SUM(總額)"),
            ReportFieldRequirement("total_amount_pct", "", "=總額/SUM(總額)*100"),
        ],
        formula_lineage=[],
        warnings=[],
    )


def expense_report_filters() -> list[ReportSqlFilter]:
    return [
        ReportSqlFilter("單據日期", ">=", "20260101"),
        ReportSqlFilter("單據日期", "<=", "20260331"),
        ReportSqlFilter("作廢碼", "not_equals_or_blank", "Y"),
        ReportSqlFilter("確認碼", "=", "Y"),
    ]


def expense_report_sql(source_dir: str = "_Source") -> str:
    return build_report_select_sql(
        PROMPT,
        load_schema_bundle(source_dir),
        expense_report_requirement(),
        filters=expense_report_filters(),
        sorts=[ReportSqlSort("total_amount", "DESC")],
    )


if __name__ == "__main__":
    print(expense_report_sql())
