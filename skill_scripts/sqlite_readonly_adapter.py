import re

from skill_scripts.postgres_readonly_adapter import (
    _quote_wferp_columns,
    _reject_unsafe_sql,
    _translate_top,
)


def _translate_sqlserver_tables(sql: str) -> str:
    translated = re.sub(
        r"\[[A-Za-z_][A-Za-z0-9_]*\]\.\[dbo\]\.\[([A-Za-z_][A-Za-z0-9_]*)\]",
        r'"\1"',
        sql,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"\[dbo\]\.\[([A-Za-z_][A-Za-z0-9_]*)\]",
        r'"\1"',
        translated,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\[([A-Za-z_][A-Za-z0-9_]*)\]", r'"\1"', translated)


def translate_sqlserver_select_to_sqlite(sql: str) -> str:
    _reject_unsafe_sql(sql)
    translated = str(sql).strip()
    translated = _translate_top(translated)
    translated = _translate_sqlserver_tables(translated)
    translated = _quote_wferp_columns(translated)
    translated = re.sub(r"\bISNULL\s*\(", "COALESCE(", translated, flags=re.IGNORECASE)
    _reject_unsafe_sql(translated)
    return translated
