from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from skill_scripts.excel_intake import WorkbookRequirement
from skill_scripts.relationship_graph import infer_relationships
from skill_scripts.sql2000_guard import validate_sql


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class ReportSqlFilter:
    field_name: str
    operator: str
    value: str


@dataclass(frozen=True)
class ReportSqlSort:
    output_name: str
    direction: str = "DESC"


def _safe_identifier(name: str) -> str:
    return f"[{str(name).strip()}]"


def _format_table_3part(db_prefix: str, table_id: str) -> str:
    db = str(db_prefix or "").strip().rstrip(".")
    parts = [part for part in db.split(".") if part]
    if len(parts) >= 2:
        db_name, schema = parts[0], parts[1]
    elif len(parts) == 1:
        db_name, schema = parts[0], "dbo"
    else:
        db_name, schema = "DSCSYS", "dbo"
    return f"{_safe_identifier(db_name)}.{_safe_identifier(schema)}.{_safe_identifier(table_id)}"


def _table_rows(bundle: JsonDict) -> dict[str, JsonDict]:
    return {
        str(table.get("TableID", "")).strip().upper(): table
        for table in bundle.get("tables", [])
        if str(table.get("TableID", "")).strip()
    }


def _field_exists(bundle: JsonDict, table_id: str, field_id: str) -> bool:
    for field in bundle.get("fields", []):
        current_table = str(field.get("TableID", "")).strip().upper()
        current_id = str(field.get("ID", "") or field.get("FieldID", "")).strip().upper()
        if current_table == table_id.upper() and current_id == field_id.upper():
            return True
    return False


def _validate_required_fields(bundle: JsonDict, requirement: WorkbookRequirement) -> None:
    tables = _table_rows(bundle)
    for field in requirement.database_fields:
        table_id = field.table.strip().upper()
        field_id = field.field.strip().upper()
        if table_id not in tables:
            raise ValueError(f"SCHEMA_TABLE_NOT_FOUND:{field.table}")
        if not _field_exists(bundle, table_id, field_id):
            raise ValueError(f"SCHEMA_FIELD_NOT_FOUND:{field.table}.{field.field}")


def _required_tables(requirement: WorkbookRequirement) -> list[str]:
    tables: list[str] = []
    for field in requirement.database_fields:
        table_id = field.table.strip().upper()
        if table_id and table_id not in tables:
            tables.append(table_id)
    return tables


def _relationship_for(bundle: JsonDict, tables: list[str]) -> JsonDict | None:
    if len(tables) != 2:
        return None
    for edge in infer_relationships(bundle.get("fields", []), bundle.get("index_keys", [])):
        from_table = str(edge.get("from_table", "")).strip().upper()
        to_table = str(edge.get("to_table", "")).strip().upper()
        if {from_table, to_table} == set(tables):
            return edge
    return None


def _aliases(bundle: JsonDict, tables: list[str]) -> tuple[dict[str, str], str, str, list[str]]:
    table_rows = _table_rows(bundle)
    if len(tables) == 1:
        table = table_rows[tables[0]]
        from_clause = f"FROM {_format_table_3part(str(table.get('DB', '')), tables[0])} header"
        return {tables[0]: "header"}, from_clause, from_clause, []

    edge = _relationship_for(bundle, tables)
    if not edge:
        raise ValueError(f"SCHEMA_RELATIONSHIP_NOT_FOUND:{','.join(tables)}")

    parent = str(edge["from_table"]).strip().upper()
    child = str(edge["to_table"]).strip().upper()
    parent_row = table_rows[parent]
    child_row = table_rows[child]
    join_conditions = [
        f"header.{_safe_identifier(left)} = detail.{_safe_identifier(right)}"
        for left, right in zip(edge["from_columns"], edge["to_columns"], strict=False)
    ]
    join_sql = (
        f"FROM {_format_table_3part(str(parent_row.get('DB', '')), parent)} header\n"
        f"JOIN {_format_table_3part(str(child_row.get('DB', '')), child)} detail\n"
        f"    ON {' AND '.join(join_conditions)}"
    )
    return {parent: "header", child: "detail"}, join_sql, join_sql, join_conditions


def _display_map(requirement: WorkbookRequirement, aliases: dict[str, str]) -> dict[str, tuple[str, str]]:
    mapping: dict[str, tuple[str, str]] = {}
    for field in requirement.database_fields:
        if not field.display_name or field.display_name in mapping:
            continue
        table_id = field.table.strip().upper()
        mapping[field.display_name] = (aliases[table_id], field.field.strip().upper())
    return mapping


def _formula_map(requirement: WorkbookRequirement) -> dict[str, str]:
    return {field.name: field.formula.lstrip("=").strip() for field in requirement.formula_fields}


def _replace_names(body: str, resolver) -> str:
    names = sorted(resolver.names(), key=len, reverse=True)
    rendered = body
    for name in names:
        if name not in rendered:
            continue
        rendered = rendered.replace(name, resolver.resolve(name))
    return rendered


class _ExpressionResolver:
    def __init__(
        self,
        display_fields: dict[str, tuple[str, str]],
        formulas: dict[str, str],
        alias_overrides: dict[str, str] | None = None,
    ):
        self.display_fields = display_fields
        self.formulas = formulas
        self.alias_overrides = alias_overrides or {}
        self._resolving: set[str] = set()

    def names(self) -> set[str]:
        return set(self.display_fields) | set(self.formulas)

    def resolve(self, name: str) -> str:
        if name in self.display_fields:
            alias, field_id = self.display_fields[name]
            alias = self.alias_overrides.get(alias, alias)
            return f"{alias}.{_safe_identifier(field_id)}"
        if name in self.formulas:
            if name in self._resolving:
                raise ValueError(f"FORMULA_CYCLE:{name}")
            self._resolving.add(name)
            try:
                return _replace_names(self.formulas[name], self)
            finally:
                self._resolving.remove(name)
        raise ValueError(f"FORMULA_REFERENCE_NOT_FOUND:{name}")


def _expand_expression(body: str, resolver: _ExpressionResolver) -> str:
    expanded = _replace_names(body.lstrip("=").strip(), resolver)
    return re.sub(r"\s*([+\-*/])\s*", r" \1 ", expanded).strip()


def _compile_filter(filter_item: ReportSqlFilter, resolver: _ExpressionResolver) -> str:
    left = resolver.resolve(filter_item.field_name)
    operator = filter_item.operator.strip().lower()
    value = str(filter_item.value).replace("'", "''")
    if operator in {"=", ">=", "<=", ">", "<"}:
        return f"{left} {operator} '{value}'"
    if operator == "not_equals_or_blank":
        return f"ISNULL({left}, '') <> '{value}'"
    raise ValueError(f"UNSUPPORTED_FILTER_OPERATOR:{filter_item.operator}")


def _compile_report_field(
    output_name: str,
    source_name: str,
    formula: str,
    resolver: _ExpressionResolver,
    grand_resolver: _ExpressionResolver,
) -> tuple[str, str | None, str | None]:
    if source_name:
        expr = resolver.resolve(source_name)
        return f"{expr} AS {output_name}", expr, None

    body = formula.lstrip("=").replace(" ", "")
    sum_match = re.fullmatch(r"SUM\((.+)\)", body, flags=re.IGNORECASE)
    if sum_match:
        expr = _expand_expression(sum_match.group(1), resolver)
        return f"SUM({expr}) AS {output_name}", None, None

    pct_match = re.fullmatch(r"(.+)/SUM\(\1\)\*100", body, flags=re.IGNORECASE)
    if pct_match:
        base_name = pct_match.group(1)
        numerator = _expand_expression(base_name, resolver)
        denominator = _expand_expression(base_name, grand_resolver)
        return (
            "CAST(\n"
            "        CASE\n"
            "            WHEN grand.grand_total_amount = 0 THEN 0\n"
            f"            ELSE SUM({numerator}) * 100.0 / grand.grand_total_amount\n"
            "        END AS decimal(18, 4)\n"
            f"    ) AS {output_name}",
            None,
            denominator,
        )

    expr = _expand_expression(body, resolver)
    return f"{expr} AS {output_name}", None, None


def build_report_select_sql(
    prompt: str,
    bundle: JsonDict,
    requirement: WorkbookRequirement,
    *,
    filters: list[ReportSqlFilter] | None = None,
    sorts: list[ReportSqlSort] | None = None,
) -> str:
    del prompt
    _validate_required_fields(bundle, requirement)
    tables = _required_tables(requirement)
    aliases, join_sql, _, _ = _aliases(bundle, tables)
    display_fields = _display_map(requirement, aliases)
    formulas = _formula_map(requirement)
    resolver = _ExpressionResolver(display_fields, formulas)
    grand_resolver = _ExpressionResolver(
        display_fields,
        formulas,
        {"header": "grand_header", "detail": "grand_detail"},
    )

    select_items = []
    group_by = []
    grand_total_expr = None
    for report_field in requirement.report_fields:
        select_sql, group_expr, denominator_expr = _compile_report_field(
            report_field.output_name,
            report_field.source_name,
            report_field.formula,
            resolver,
            grand_resolver,
        )
        select_items.append(select_sql)
        if group_expr:
            group_by.append(group_expr)
        if denominator_expr:
            grand_total_expr = denominator_expr
            if "grand.grand_total_amount" not in group_by:
                group_by.append("grand.grand_total_amount")

    where_items = [_compile_filter(filter_item, resolver) for filter_item in filters or []]
    where_sql = f"\nWHERE {' AND '.join(where_items)}" if where_items else ""
    group_sql = f"\nGROUP BY {', '.join(group_by)}" if group_by else ""
    order_items = []
    for sort in sorts or []:
        direction = sort.direction.strip().upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError(f"UNSUPPORTED_SORT_DIRECTION:{sort.direction}")
        order_items.append(f"{sort.output_name} {direction}")
    order_sql = f"\nORDER BY {', '.join(order_items)}" if order_items else ""

    if grand_total_expr:
        grand_join_sql = join_sql.replace(" header", " grand_header").replace(" detail", " grand_detail")
        grand_where_items = [
            _compile_filter(
                filter_item,
                _ExpressionResolver(
                    display_fields,
                    formulas,
                    {"header": "grand_header", "detail": "grand_detail"},
                ),
            )
            for filter_item in filters or []
        ]
        grand_where_sql = f"\n    WHERE {' AND '.join(grand_where_items)}" if grand_where_items else ""
        cross_join = (
            "\nCROSS JOIN (\n"
            f"    SELECT SUM({grand_total_expr}) AS grand_total_amount\n"
            f"    {grand_join_sql.replace(chr(10), chr(10) + '    ')}"
            f"{grand_where_sql}\n"
            ") grand"
        )
        select_items = [
            item if "grand.grand_total_amount" not in item else item
            for item in select_items
        ]
    else:
        cross_join = ""

    sql = (
        "SELECT\n    "
        + ",\n    ".join(select_items)
        + "\n"
        + join_sql
        + cross_join
        + where_sql
        + group_sql
        + order_sql
    )
    ok, code = validate_sql(sql)
    if not ok:
        raise ValueError(code)
    return sql
