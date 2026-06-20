import re


class PostgresReadonlyAdapterError(ValueError):
    pass


BLOCKED_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "EXEC",
    "MERGE",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
)

_WFERP_COLUMN_PATTERN = re.compile(r"\b((?:grand_header|grand_detail|header|detail)\.)?(T[AB]\d{3})\b")


def _reject_unsafe_sql(sql: str) -> None:
    text = str(sql or "").strip()
    upper = text.upper()
    if not text:
        raise PostgresReadonlyAdapterError("EMPTY_SQL")
    if not upper.startswith("SELECT"):
        raise PostgresReadonlyAdapterError("NON_SELECT_SQL")
    if ";" in text:
        raise PostgresReadonlyAdapterError("MULTI_STATEMENT_NOT_ALLOWED")
    if "--" in text or "/*" in text or "*/" in text:
        raise PostgresReadonlyAdapterError("COMMENTS_NOT_ALLOWED")
    if re.search(r"(?<![A-Z0-9_])XP_[A-Z0-9_]*", upper):
        raise PostgresReadonlyAdapterError("SQL_SERVER_EXTENDED_PROCEDURE_NOT_ALLOWED")
    if re.search(r"\bINTO\b", upper):
        raise PostgresReadonlyAdapterError("SELECT_INTO_NOT_ALLOWED")
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            raise PostgresReadonlyAdapterError(f"BLOCKED_KEYWORD:{keyword}")


def _translate_top(sql: str) -> str:
    match = re.match(r"(?is)^\s*SELECT\s+TOP\s+(\d+)\s+(.*)$", sql)
    if not match:
        return sql
    limit = match.group(1)
    body = match.group(2).strip()
    return f"SELECT {body} LIMIT {limit}"


def _translate_schema_identifiers(sql: str) -> str:
    translated = re.sub(
        r"\[[A-Za-z_][A-Za-z0-9_]*\]\.\[dbo\]\.\[([A-Za-z_][A-Za-z0-9_]*)\]",
        r'dbo."\1"',
        sql,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"\[dbo\]\.\[([A-Za-z_][A-Za-z0-9_]*)\]",
        r'dbo."\1"',
        translated,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\[([A-Za-z_][A-Za-z0-9_]*)\]", r'"\1"', translated)


def _quote_wferp_columns(sql: str) -> str:
    def replace(match: re.Match[str]) -> str:
        prefix = match.group(1) or ""
        column = match.group(2)
        start = match.start(2)
        end = match.end(2)
        if start > 0 and sql[start - 1] == '"':
            return match.group(0)
        if end < len(sql) and sql[end : end + 1] == '"':
            return match.group(0)
        return f'{prefix}"{column}"'

    return _WFERP_COLUMN_PATTERN.sub(replace, sql)


def translate_sqlserver_select_to_postgres(sql: str) -> str:
    _reject_unsafe_sql(sql)
    translated = str(sql).strip()
    translated = _translate_top(translated)
    translated = _translate_schema_identifiers(translated)
    translated = _quote_wferp_columns(translated)
    translated = re.sub(r"\bISNULL\s*\(", "COALESCE(", translated, flags=re.IGNORECASE)
    _reject_unsafe_sql(translated)
    return translated
