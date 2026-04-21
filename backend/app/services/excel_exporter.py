from pathlib import Path

import pandas as pd

from app.schemas import ParseResult


def export_excel(parse_result: ParseResult, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    primary_table_rows = build_primary_table_rows(parse_result)
    structured_rows = build_structured_rows(parse_result)
    issue_rows = build_issue_rows(parse_result)
    raw_rows = build_raw_rows(parse_result)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(primary_table_rows).to_excel(writer, sheet_name="原始明细", index=False)
        pd.DataFrame(structured_rows).to_excel(writer, sheet_name="结构化字段", index=False)
        pd.DataFrame(issue_rows).to_excel(writer, sheet_name="错误与低置信字段", index=False)
        pd.DataFrame(raw_rows).to_excel(writer, sheet_name="原始抽取日志", index=False)

    return output_path


def build_primary_table_rows(parse_result: ParseResult) -> list[dict[str, str]]:
    if not parse_result.tables:
        return build_structured_rows(parse_result)

    primary_table = max(parse_result.tables, key=lambda table: (len(table.rows), len(table.columns)))
    return [{column: row.get(column, "") for column in primary_table.columns} for row in primary_table.rows]


def build_structured_rows(parse_result: ParseResult) -> list[dict[str, str | int | float]]:
    if parse_result.tables:
        rows: list[dict[str, str | int | float]] = []
        for table_index, table in enumerate(parse_result.tables, start=1):
            for row_index, row in enumerate(table.rows, start=1):
                rows.append(
                    {
                        "table_index": table_index,
                        "row_index": row_index,
                        "page_no": table.page_no,
                        "confidence": table.confidence,
                        **{column: row.get(column, "") for column in table.columns},
                    }
                )
        return rows

    return [
        {
            "field_key": field.field_key,
            "field_value": field.field_value,
            "confidence": field.confidence,
            "page_no": field.page_no,
            "source_type": field.source_type,
        }
        for field in parse_result.fields
    ]


def build_issue_rows(parse_result: ParseResult) -> list[dict[str, str | int | None]]:
    return [
        {
            "rule": issue.rule,
            "message": issue.message,
            "severity": issue.severity,
            "page_no": issue.page_no,
            "field_key": issue.field_key,
            "table_row": issue.table_row,
        }
        for issue in parse_result.validation_issues
    ]


def build_raw_rows(parse_result: ParseResult) -> list[dict[str, str | int | float]]:
    raw_rows = [
        {
            "field_key": field.field_key,
            "field_value": field.field_value,
            "confidence": field.confidence,
            "bbox": ",".join(str(item) for item in field.bbox),
            "page_no": field.page_no,
            "source_type": field.source_type,
        }
        for field in parse_result.fields
    ]

    for table_index, table in enumerate(parse_result.tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            raw_rows.append(
                {
                    "field_key": f"table_{table_index}_row_{row_index}",
                    "field_value": str(row),
                    "confidence": table.confidence,
                    "bbox": "",
                    "page_no": table.page_no,
                    "source_type": "table",
                }
            )

    return raw_rows
