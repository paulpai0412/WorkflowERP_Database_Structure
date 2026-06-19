from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MISSING_DESCRIPTION = "schema description missing"


class SchemaMetadata:
    def __init__(self, table_names: dict[str, str], field_names: dict[tuple[str, str], str]):
        self._table_names = table_names
        self._field_names = field_names

    @classmethod
    def from_source_dir(cls, source_dir: str | Path) -> "SchemaMetadata":
        source = Path(source_dir)
        table_rows = json.loads((source / "TableName.json").read_text(encoding="utf-8"))
        field_rows = json.loads((source / "TableStructure.json").read_text(encoding="utf-8"))

        table_names: dict[str, str] = {}
        for row in table_rows:
            table_id = str(row.get("TableID", "")).strip().upper()
            table_name = str(row.get("TableName", "") or row.get("TableNameCHT", "") or "").strip()
            if table_id:
                table_names[table_id] = table_name or MISSING_DESCRIPTION

        field_names: dict[tuple[str, str], str] = {}
        for row in field_rows:
            table_id = str(row.get("TableID", "")).strip().upper()
            column_id = str(row.get("ID", "")).strip().upper()
            column_name = str(row.get("FieldName", "") or row.get("Name", "") or "").strip()
            if table_id and column_id:
                field_names[(table_id, column_id)] = column_name or MISSING_DESCRIPTION

        return cls(table_names, field_names)

    def describe_field(
        self,
        table_id: str,
        column_id: str,
        join_reason: str = "",
        business_meaning: str = "",
    ) -> dict[str, Any]:
        table_key = table_id.strip().upper()
        column_key = column_id.strip().upper()
        table_name = self._table_names.get(table_key, MISSING_DESCRIPTION)
        column_name = self._field_names.get((table_key, column_key), MISSING_DESCRIPTION)
        metadata_status = (
            "ok" if table_name != MISSING_DESCRIPTION and column_name != MISSING_DESCRIPTION else "warning"
        )
        meaning = business_meaning.strip() if business_meaning else f"{table_key}.{column_key} from WFERP schema"

        return {
            "table_id": table_key,
            "table_name": table_name,
            "column_id": column_key,
            "column_name": column_name,
            "join_reason": join_reason,
            "business_meaning": meaning,
            "metadata_status": metadata_status,
        }

    def describe_expression(self, inputs: list[dict[str, Any]]) -> dict[str, Any]:
        described_inputs = [
            self.describe_field(
                str(item.get("table_id", "")),
                str(item.get("column_id", "")),
                business_meaning=str(item.get("reason", "")),
            )
            for item in inputs
        ]
        metadata_status = (
            "warning"
            if any(item["metadata_status"] == "warning" for item in described_inputs)
            else "ok"
        )
        return {"inputs": described_inputs, "metadata_status": metadata_status}
