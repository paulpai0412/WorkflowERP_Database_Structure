from __future__ import annotations

from skill_scripts.schema_metadata import SchemaMetadata


def test_describe_field_returns_readable_table_and_column_names():
    metadata = SchemaMetadata.from_source_dir("_Source")

    field = metadata.describe_field("ACTML", "ML006")

    assert field["table_id"] == "ACTML"
    assert field["column_id"] == "ML006"
    assert field["table_name"] == "分類帳檔"
    assert field["column_name"] == "明細科目編號"
    assert field["metadata_status"] == "ok"


def test_describe_missing_field_returns_warning_not_bare_code():
    metadata = SchemaMetadata.from_source_dir("_Source")

    field = metadata.describe_field("ACTML", "ZZ999")

    assert field["table_id"] == "ACTML"
    assert field["column_id"] == "ZZ999"
    assert field["column_name"] == "schema description missing"
    assert field["metadata_status"] == "warning"
    assert "ZZ999" in field["business_meaning"]


def test_describe_expression_includes_each_input_field():
    metadata = SchemaMetadata.from_source_dir("_Source")

    expression = metadata.describe_expression(
        [
            {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
            {"table_id": "ACTML", "column_id": "ML014", "reason": "原幣金額"},
        ]
    )

    assert expression["metadata_status"] == "ok"
    assert expression["inputs"] == [
        {
            "table_id": "ACTML",
            "table_name": "分類帳檔",
            "column_id": "ML007",
            "column_name": "借貸別",
            "join_reason": "",
            "business_meaning": "借貸別",
            "metadata_status": "ok",
        },
        {
            "table_id": "ACTML",
            "table_name": "分類帳檔",
            "column_id": "ML014",
            "column_name": "原幣金額",
            "join_reason": "",
            "business_meaning": "原幣金額",
            "metadata_status": "ok",
        },
    ]


def test_describe_expression_warns_when_any_input_field_is_missing():
    metadata = SchemaMetadata.from_source_dir("_Source")

    expression = metadata.describe_expression(
        [
            {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
            {"table_id": "ACTML", "column_id": "ZZ999", "reason": "Excel 公式來源欄位"},
        ]
    )

    assert expression["metadata_status"] == "warning"
    assert expression["inputs"][0]["metadata_status"] == "ok"
    assert expression["inputs"][1]["column_name"] == "schema description missing"
    assert expression["inputs"][1]["business_meaning"] == "Excel 公式來源欄位"
    assert expression["inputs"][1]["metadata_status"] == "warning"
