import json
import logging
import re
import base64
from dataclasses import dataclass
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

import fitz
import pdfplumber
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from app.config import get_settings
from app.schemas import FieldItem, PagePreview, ParseResult, ParseStats, TableItem, ValidationIssue
from app.services.excel_exporter import export_excel

logger = logging.getLogger(__name__)
settings = get_settings()

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
IMAGE_PDF_RESOLUTION = 72.0
MODEL_CODE_CORRECTIONS = {
    "TMG5N": "TM65N",
    "TM8SN": "TM85N",
    "TESON": "TE50N",
    "TESSN": "TE55N",
    "TEGSN": "TE65N",
}

DATE_PATTERN = re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})")
AMOUNT_PATTERN = re.compile(r"(?<!\d)(?:¥|￥|\$)?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?(?!\d)")
ORDER_PATTERN = re.compile(r"\b(?:SO|PO|INV|NO|ORDER|订单)[-_:# ]*[A-Z0-9-]{4,}\b", re.IGNORECASE)
KEY_VALUE_PATTERN = re.compile(r"^\s*([^:：]{2,40})[:：]\s*(.+?)\s*$")
NUMERIC_PATTERN = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
OCR_ENGINE: RapidOCR | None = None


@dataclass
class OCRDetection:
    text: str
    confidence: float
    bbox: list[float]
    page_no: int


@dataclass
class VisionExtraction:
    fields: list[FieldItem]
    tables: list[TableItem]


def parse_pdf(pdf_path: Path, static_dir: Path, export_dir: Path, document_id: int) -> ParseResult:
    logger.info("Parsing PDF: %s", pdf_path)
    pdf_type = detect_pdf_type(pdf_path)
    page_previews = render_page_images(pdf_path, static_dir, document_id)
    if pdf_type == "scanned":
        text_fields, tables = extract_scanned_content(static_dir, document_id, page_previews)
    else:
        ocr_pages: dict[int, list[OCRDetection]] = {}
        text_fields = extract_text_blocks(pdf_path, pdf_type, ocr_pages)
        tables = extract_tables(pdf_path, pdf_type, ocr_pages)
    normalized_fields = normalize_fields(text_fields, tables, pdf_type)
    validation_issues = validate_fields(normalized_fields, tables)

    result = ParseResult(
        pdf_type=pdf_type,
        fields=normalized_fields,
        tables=tables,
        validation_issues=validation_issues,
        pages=page_previews,
        stats=ParseStats(
            field_count=len(normalized_fields),
            table_count=len(tables),
            low_confidence_count=sum(1 for field in normalized_fields if field.confidence < 0.75),
            error_count=sum(1 for issue in validation_issues if issue.severity == "error"),
        ),
    )

    export_path = export_dir / f"document_{document_id}_{uuid4().hex[:8]}.xlsx"
    export_excel(result, export_path)
    logger.info("Excel prepared: %s", export_path)
    return result


def extract_scanned_content(
    static_dir: Path,
    document_id: int,
    page_previews: list[PagePreview],
) -> tuple[list[FieldItem], list[TableItem]]:
    vision_result = extract_with_moonshot(static_dir, document_id, page_previews)
    if vision_result and (vision_result.tables or vision_result.fields):
        logger.info("Moonshot vision extraction succeeded for document %s", document_id)
        return vision_result.fields, vision_result.tables

    logger.info("Moonshot vision extraction unavailable or empty; falling back to OCR for document %s", document_id)
    ocr_pages = run_ocr_on_pages(static_dir, document_id, page_previews)
    return extract_ocr_fields(ocr_pages), extract_ocr_tables(ocr_pages)


def ensure_pdf_input(source_path: Path) -> Path:
    if source_path.suffix.lower() == ".pdf":
        return source_path
    if source_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {source_path.suffix}")

    output_path = source_path.with_suffix(".pdf")
    with Image.open(source_path) as image:
        rgb_image = image.convert("RGB")
        rgb_image.save(output_path, "PDF", resolution=IMAGE_PDF_RESOLUTION)
    return output_path


def detect_pdf_type(pdf_path: Path) -> str:
    with fitz.open(pdf_path) as doc:
        total_text_length = 0
        image_count = 0
        for page in doc:
            total_text_length += len(page.get_text("text").strip())
            image_count += len(page.get_images())

    if total_text_length > 80:
        return "digital"
    if image_count > 0:
        return "scanned"
    return "digital"


def extract_text_blocks(
    pdf_path: Path,
    pdf_type: str,
    ocr_pages: dict[int, list[OCRDetection]] | None = None,
) -> list[FieldItem]:
    if pdf_type == "scanned":
        return extract_ocr_fields(ocr_pages or {})

    fields: list[FieldItem] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            blocks = page.get_text("blocks")
            for block in blocks:
                x0, y0, x1, y1, text, *_ = block
                clean_text = " ".join(text.split())
                if not clean_text:
                    continue

                fields.extend(field_candidates_from_text(clean_text, [x0, y0, x1, y1], page_index))

                fields.append(
                    FieldItem(
                        field_key=f"raw_text_block_{page_index}_{len(fields) + 1}",
                        field_value=clean_text[:500],
                        confidence=0.7,
                        bbox=[x0, y0, x1, y1],
                        page_no=page_index,
                        source_type="text",
                    )
                )
    return deduplicate_fields(fields)


def extract_tables(
    pdf_path: Path,
    pdf_type: str,
    ocr_pages: dict[int, list[OCRDetection]] | None = None,
) -> list[TableItem]:
    if pdf_type == "scanned":
        return extract_ocr_tables(ocr_pages or {})

    tables: list[TableItem] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            try:
                extracted_tables = page.extract_tables() or []
            except Exception as exc:
                logger.warning("Failed to extract tables on page %s: %s", page_index, exc)
                extracted_tables = []

            for raw_table in extracted_tables:
                if not raw_table or len(raw_table) < 2:
                    continue

                headers = [normalize_cell_name(cell, f"column_{idx + 1}") for idx, cell in enumerate(raw_table[0])]
                rows: list[dict[str, str]] = []
                for row in raw_table[1:]:
                    row_map: dict[str, str] = {}
                    for idx, cell in enumerate(row):
                        header = headers[idx] if idx < len(headers) else f"column_{idx + 1}"
                        row_map[header] = "" if cell is None else str(cell).strip()
                    if any(value for value in row_map.values()):
                        rows.append(row_map)

                if rows:
                    tables.append(
                        TableItem(columns=headers, rows=rows, page_no=page_index, confidence=0.86)
                    )
    return tables


def normalize_fields(text_fields: list[FieldItem], tables: list[TableItem], pdf_type: str) -> list[FieldItem]:
    normalized = list(text_fields)

    for table_index, table in enumerate(tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            for column_name, value in row.items():
                if not value:
                    continue
                normalized.append(
                    FieldItem(
                        field_key=f"table_{table_index}.row_{row_index}.{slugify(column_name)}",
                        field_value=value,
                        confidence=min(table.confidence, 0.83),
                        bbox=[0, 0, 0, 0],
                        page_no=table.page_no,
                        source_type="table",
                    )
                )

    if pdf_type == "scanned" and not normalized:
        normalized.append(
            FieldItem(
                field_key="ocr_pending",
                field_value="Scanned PDF detected, but OCR did not return usable text.",
                confidence=0.3,
                bbox=[0, 0, 0, 0],
                page_no=1,
                source_type="ocr",
            )
        )

    return deduplicate_fields(normalized)


def validate_fields(fields: list[FieldItem], tables: list[TableItem]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for field in fields:
        if field.confidence < 0.6:
            issues.append(
                ValidationIssue(
                    rule="low_confidence",
                    message=f"{field.field_key} confidence is below recommended threshold.",
                    severity="warning",
                    page_no=field.page_no,
                    field_key=field.field_key,
                )
            )

        if "date" in field.field_key.lower() and not DATE_PATTERN.search(field.field_value):
            issues.append(
                ValidationIssue(
                    rule="date_format",
                    message=f"{field.field_key} does not match a valid date format.",
                    severity="error",
                    page_no=field.page_no,
                    field_key=field.field_key,
                )
            )

        if any(token in field.field_key.lower() for token in ["amount", "total", "price", "unit_price"]) and not AMOUNT_PATTERN.search(
            field.field_value
        ):
            issues.append(
                ValidationIssue(
                    rule="amount_format",
                    message=f"{field.field_key} does not look like a valid amount.",
                    severity="error",
                    page_no=field.page_no,
                    field_key=field.field_key,
                )
            )

    for table in tables:
        row_totals = []
        for row_index, row in enumerate(table.rows, start=1):
            qty = find_numeric_value(row, ["qty", "quantity", "数量"])
            unit_price = find_numeric_value(row, ["unit_price", "price", "单价"])
            amount = find_numeric_value(row, ["amount", "total", "金额"])

            if qty is not None and unit_price is not None and amount is not None:
                if abs(qty * unit_price - amount) > 0.05:
                    issues.append(
                        ValidationIssue(
                            rule="line_amount_check",
                            message=f"Row {row_index} failed Qty * unit_price ≈ amount.",
                            severity="error",
                            page_no=table.page_no,
                            table_row=row_index,
                        )
                    )
                row_totals.append(amount)

        summary_total = extract_summary_total(fields, table.page_no)
        if row_totals and summary_total is not None:
            if abs(sum(row_totals) - summary_total) > 0.1:
                issues.append(
                    ValidationIssue(
                        rule="summary_total_check",
                        message="Summary total does not equal the sum of table amounts.",
                        severity="error",
                        page_no=table.page_no,
                    )
                )

    return issues


def render_page_images(pdf_path: Path, static_dir: Path, document_id: int) -> list[PagePreview]:
    output_dir = static_dir / f"document_{document_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    previews: list[PagePreview] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            zoom = 2
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            output_path = output_dir / f"page_{page_index}.png"
            pix.save(output_path)
            previews.append(
                PagePreview(
                    page_no=page_index,
                    image_url=f"/static/document_{document_id}/page_{page_index}.png",
                    width=page.rect.width,
                    height=page.rect.height,
                )
            )
    return previews


def run_ocr_placeholder() -> list[FieldItem]:
    return [
        FieldItem(
            field_key="ocr_status",
            field_value="OCR pipeline placeholder. Integrate an OCR engine here for scanned PDFs.",
            confidence=0.25,
            bbox=[0, 0, 0, 0],
            page_no=1,
            source_type="ocr",
        )
    ]


def extract_with_moonshot(
    static_dir: Path,
    document_id: int,
    page_previews: list[PagePreview],
) -> VisionExtraction | None:
    if not settings.moonshot_api_key:
        return None

    all_fields: list[FieldItem] = []
    all_tables: list[TableItem] = []
    for preview in page_previews:
        image_path = static_dir / f"document_{document_id}" / f"page_{preview.page_no}.png"
        page_result = call_moonshot_table_extraction(image_path, preview.page_no)
        if page_result is None:
            return None
        all_fields.extend(page_result.fields)
        all_tables.extend(page_result.tables)

    return VisionExtraction(fields=all_fields, tables=all_tables)


def call_moonshot_table_extraction(image_path: Path, page_no: int) -> VisionExtraction | None:
    image_base64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    model_name = settings.default_model_name.replace("moonshot/", "", 1)
    image_url = f"data:image/{image_path.suffix.lstrip('.').lower()};base64,{image_base64}"
    prompt = (
        "Extract the document into strict JSON.\n"
        "Prioritize exact table reconstruction for spreadsheet-like images.\n"
        "Preserve headers and cell values exactly as visible, including spaces, currency symbols, punctuation, and month text.\n"
        "Do not translate headers. Do not normalize values. Do not merge or split rows unless visually obvious.\n"
        "If the page is mainly a table, put the content into tables and keep fields minimal.\n"
        "Return JSON only using this shape:\n"
        "{"
        "\"fields\":[{\"field_key\":\"\",\"field_value\":\"\",\"confidence\":0.0,\"bbox\":[0,0,0,0],\"page_no\":1,\"source_type\":\"ocr\"}],"
        "\"tables\":[{\"columns\":[],\"rows\":[],\"page_no\":1,\"confidence\":0.0}]"
        "}"
    )
    payload = {
        "model": model_name,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": "You are a precise document table extraction engine. Output valid JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            },
        ],
    }

    response_payload = request_moonshot_chat_completion(payload)
    if response_payload is None:
        return None

    content = extract_message_content(response_payload)
    if not content:
        return None

    parsed = parse_json_object(content)
    if parsed is None:
        logger.warning("Moonshot returned non-JSON content")
        return None

    return vision_payload_to_result(parsed, page_no)


def request_moonshot_chat_completion(payload: dict[str, object]) -> dict[str, object] | None:
    tried_urls: set[str] = set()
    base_urls = [settings.moonshot_base_url]
    if "api.moonshot.ai" in settings.moonshot_base_url:
        base_urls.append(settings.moonshot_base_url.replace("api.moonshot.ai", "api.moonshot.cn"))
    elif "api.moonshot.cn" in settings.moonshot_base_url:
        base_urls.append(settings.moonshot_base_url.replace("api.moonshot.cn", "api.moonshot.ai"))

    for base_url in base_urls:
        request_url = f"{base_url.rstrip('/')}/chat/completions"
        if request_url in tried_urls:
            continue
        tried_urls.add(request_url)
        request = urllib_request.Request(
            url=request_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.moonshot_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            logger.warning("Moonshot request failed via %s with status %s: %s", base_url, exc.code, body[:500])
        except Exception as exc:
            logger.warning("Moonshot request failed via %s: %s", base_url, exc)

    return None


def extract_message_content(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "\n".join(text_parts)
    return ""


def parse_json_object(content: str) -> dict[str, object] | None:
    stripped = content.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None


def vision_payload_to_result(payload: dict[str, object], page_no: int) -> VisionExtraction:
    fields: list[FieldItem] = []
    tables: list[TableItem] = []

    raw_fields = payload.get("fields", [])
    if isinstance(raw_fields, list):
        for index, item in enumerate(raw_fields):
            if not isinstance(item, dict):
                continue
            fields.append(
                FieldItem(
                    field_key=str(item.get("field_key", f"vision_field_{index + 1}")).strip() or f"vision_field_{index + 1}",
                    field_value=str(item.get("field_value", "")).strip(),
                    confidence=clamp_confidence(item.get("confidence", 0.9)),
                    bbox=normalize_bbox(item.get("bbox", [0, 0, 0, 0])),
                    page_no=int(item.get("page_no", page_no) or page_no),
                    source_type="ocr",
                )
            )

    raw_tables = payload.get("tables", [])
    if isinstance(raw_tables, list):
        for item in raw_tables:
            if not isinstance(item, dict):
                continue
            columns = [str(column).strip() for column in item.get("columns", []) if str(column).strip()]
            raw_rows = item.get("rows", [])
            if not columns or not isinstance(raw_rows, list):
                continue
            rows: list[dict[str, str]] = []
            for row in raw_rows:
                if isinstance(row, dict):
                    rows.append({column: str(row.get(column, "")).strip() for column in columns})
                elif isinstance(row, list):
                    rows.append({column: str(row[idx]).strip() if idx < len(row) else "" for idx, column in enumerate(columns)})
            if rows:
                tables.append(
                    TableItem(
                        columns=columns,
                        rows=rows,
                        page_no=int(item.get("page_no", page_no) or page_no),
                        confidence=clamp_confidence(item.get("confidence", 0.95)),
                    )
                )

    return VisionExtraction(fields=fields, tables=tables)


def get_ocr_engine() -> RapidOCR:
    global OCR_ENGINE
    if OCR_ENGINE is None:
        OCR_ENGINE = RapidOCR()
    return OCR_ENGINE


def run_ocr_on_pages(static_dir: Path, document_id: int, page_previews: list[PagePreview]) -> dict[int, list[OCRDetection]]:
    detections_by_page: dict[int, list[OCRDetection]] = {}
    ocr_engine = get_ocr_engine()

    for preview in page_previews:
        image_path = static_dir / f"document_{document_id}" / f"page_{preview.page_no}.png"
        result, _ = ocr_engine(str(image_path))
        detections: list[OCRDetection] = []
        for item in result or []:
            box, text, confidence = item
            clean_text = " ".join(str(text).split())
            if not clean_text:
                continue
            detections.append(
                OCRDetection(
                    text=clean_text,
                    confidence=float(confidence),
                    bbox=polygon_to_bbox(box),
                    page_no=preview.page_no,
                )
            )
        detections_by_page[preview.page_no] = detections

    return detections_by_page


def extract_ocr_fields(ocr_pages: dict[int, list[OCRDetection]]) -> list[FieldItem]:
    fields: list[FieldItem] = []
    for page_no, detections in ocr_pages.items():
        for detection in detections:
            fields.extend(field_candidates_from_text(detection.text, detection.bbox, page_no, source_type="ocr", base_confidence=max(0.6, detection.confidence)))
            fields.append(
                FieldItem(
                    field_key=f"raw_ocr_block_{page_no}_{len(fields) + 1}",
                    field_value=detection.text[:500],
                    confidence=max(0.55, detection.confidence),
                    bbox=detection.bbox,
                    page_no=page_no,
                    source_type="ocr",
                )
            )
    return deduplicate_fields(fields)


def extract_ocr_tables(ocr_pages: dict[int, list[OCRDetection]]) -> list[TableItem]:
    tables: list[TableItem] = []
    for page_no, detections in ocr_pages.items():
        rows = cluster_ocr_rows(detections)
        candidate = build_table_from_rows(rows, page_no)
        if candidate:
            tables.append(candidate)
    return tables


def cluster_ocr_rows(detections: list[OCRDetection]) -> list[list[OCRDetection]]:
    if not detections:
        return []

    sorted_items = sorted(detections, key=lambda item: (bbox_center_y(item.bbox), item.bbox[0]))
    avg_height = sum(item.bbox[3] - item.bbox[1] for item in sorted_items) / max(len(sorted_items), 1)
    tolerance = max(6.0, min(18.0, avg_height * 0.45))

    grouped: list[dict[str, object]] = []
    for item in sorted_items:
        item_y = bbox_center_y(item.bbox)
        placed = False
        for row in grouped:
            row_y = float(row["y"])
            if abs(row_y - item_y) <= tolerance:
                row["items"].append(item)  # type: ignore[index]
                row["y"] = (row_y + item_y) / 2
                placed = True
                break
        if not placed:
            grouped.append({"y": item_y, "items": [item]})

    normalized_rows: list[list[OCRDetection]] = []
    for row in sorted(grouped, key=lambda entry: float(entry["y"])):
        items = sorted(row["items"], key=lambda item: item.bbox[0])  # type: ignore[arg-type]
        normalized_rows.append(items)
    return normalized_rows


def merge_row_cells(items: list[OCRDetection]) -> list[OCRDetection]:
    if not items:
        return []

    merged: list[OCRDetection] = [items[0]]
    for item in items[1:]:
        previous = merged[-1]
        gap = item.bbox[0] - previous.bbox[2]
        prev_height = previous.bbox[3] - previous.bbox[1]
        current_height = item.bbox[3] - item.bbox[1]
        threshold = max(24.0, min(60.0, (prev_height + current_height) * 0.9))
        if gap <= threshold:
            merged[-1] = OCRDetection(
                text=f"{previous.text} {item.text}",
                confidence=min(previous.confidence, item.confidence),
                bbox=[
                    min(previous.bbox[0], item.bbox[0]),
                    min(previous.bbox[1], item.bbox[1]),
                    max(previous.bbox[2], item.bbox[2]),
                    max(previous.bbox[3], item.bbox[3]),
                ],
                page_no=item.page_no,
            )
        else:
            merged.append(item)
    return merged


def build_table_from_rows(rows: list[list[OCRDetection]], page_no: int) -> TableItem | None:
    header_keywords = (
        "qty",
        "amount",
        "revenue",
        "price",
        "model",
        "order",
        "customer",
        "date",
        "code",
        "designation",
        "montant",
        "commande",
        "unit",
        "单价",
        "出货",
    )

    header_index = None
    best_header_score = 0
    for index, row in enumerate(rows):
        line_text = " ".join(cell.text.lower() for cell in row)
        if len(row) < 4 or not any(keyword in line_text for keyword in header_keywords):
            continue

        header_score = score_table_header(line_text)
        if header_score > best_header_score:
            header_index = index
            best_header_score = header_score

    if header_index is None:
        return None

    header_rows = [rows[header_index]]
    if header_index + 1 < len(rows):
        next_row = rows[header_index + 1]
        next_line_text = " ".join(cell.text.lower() for cell in next_row)
        if len(next_row) <= max(3, len(rows[header_index]) // 2) and not looks_like_data_row(next_row) and any(
            keyword in next_line_text for keyword in ("customer", "custome", "order")
        ):
            header_rows.append(next_row)

    columns, column_ranges = derive_columns_from_header_rows(header_rows)
    if len(columns) < 4:
        return None

    table_rows: list[dict[str, str]] = []
    start_index = header_index + len(header_rows)
    for row in rows[start_index:]:
        if not looks_like_data_row(row) and not (table_rows and looks_like_continuation_row(row)):
            if table_rows:
                break
            continue

        assigned_items: dict[str, list[OCRDetection]] = {column: [] for column in columns}
        for cell in row:
            target_index = locate_column_index(column_ranges, bbox_center_x(cell.bbox))
            assigned_items[columns[target_index]].append(cell)

        assigned = {
            column: clean_table_cell_value(
                " ".join(item.text for item in sorted(items, key=lambda item: item.bbox[0])),
                column,
            )
            for column, items in assigned_items.items()
        }

        non_empty_count = sum(1 for value in assigned.values() if value)
        if non_empty_count >= max(3, len(columns) // 2):
            table_rows.append(assigned)

    table_rows = postprocess_table_rows([row for row in table_rows if row_has_meaningful_values(row)])
    if not table_rows:
        return None

    avg_confidence = sum(cell.confidence for row in rows[header_index : start_index + len(table_rows)] for cell in row) / max(
        sum(len(row) for row in rows[header_index : start_index + len(table_rows)]),
        1,
    )

    return TableItem(columns=columns, rows=table_rows, page_no=page_no, confidence=max(0.55, min(0.92, avg_confidence)))


def score_table_header(line_text: str) -> int:
    token_groups = (
        ("designation", "désignation"),
        ("qty", "quantité", "qte"),
        ("montant", "amount", "net revenue"),
        ("p.u", "pu", "unit", "price", "单价"),
        ("code produit", "product code", "model"),
        ("order", "commande", "customer"),
    )
    score = 0
    for group in token_groups:
        if any(token in line_text for token in group):
            score += 1

    # Detail tables usually contain both item description and quantity/amount
    # headers. Header metadata rows often contain only order/customer tokens.
    if "designation" in line_text and ("qty" in line_text or "montant" in line_text):
        score += 3
    return score


def field_candidates_from_text(
    text: str,
    bbox: list[float],
    page_no: int,
    source_type: str = "text",
    base_confidence: float = 0.95,
) -> list[FieldItem]:
    candidates: list[FieldItem] = []

    key_value_match = KEY_VALUE_PATTERN.match(text)
    if key_value_match:
        raw_key = slugify(key_value_match.group(1))
        raw_value = key_value_match.group(2).strip()
        candidates.append(
            FieldItem(
                field_key=raw_key,
                field_value=raw_value,
                confidence=min(base_confidence, 0.95),
                bbox=bbox,
                page_no=page_no,
                source_type=source_type,
            )
        )

    for match in ORDER_PATTERN.finditer(text):
        candidates.append(
            FieldItem(
                field_key="order_no",
                field_value=match.group(0),
                confidence=min(base_confidence, 0.92),
                bbox=bbox,
                page_no=page_no,
                source_type=source_type,
            )
        )

    for match in DATE_PATTERN.finditer(text):
        candidates.append(
            FieldItem(
                field_key="document_date",
                field_value=match.group(1),
                confidence=min(base_confidence, 0.9),
                bbox=bbox,
                page_no=page_no,
                source_type=source_type,
            )
        )

    amount_matches = list(AMOUNT_PATTERN.finditer(text))
    for idx, match in enumerate(amount_matches[:3], start=1):
        candidates.append(
            FieldItem(
                field_key="amount" if idx == 1 else f"amount_{idx}",
                field_value=match.group(0),
                confidence=min(base_confidence, 0.78),
                bbox=bbox,
                page_no=page_no,
                source_type=source_type,
            )
        )

    if any(token in text.lower() for token in ["customer", "client", "客户"]):
        value = text.split(":", 1)[-1].split("：", 1)[-1].strip()
        candidates.append(
            FieldItem(
                field_key="customer_name",
                field_value=value if value and value != text else text,
                confidence=min(base_confidence, 0.88),
                bbox=bbox,
                page_no=page_no,
                source_type=source_type,
            )
        )

    return candidates


def deduplicate_fields(fields: list[FieldItem]) -> list[FieldItem]:
    seen: set[tuple[str, str, int, str]] = set()
    deduped: list[FieldItem] = []
    for field in fields:
        key = (field.field_key, field.field_value, field.page_no, field.source_type)
        if key not in seen:
            deduped.append(field)
            seen.add(key)
    deduped.sort(key=lambda item: (item.page_no, item.field_key, -item.confidence))
    return deduped


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fa5]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "field"


def normalize_cell_name(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    clean = " ".join(str(value).split())
    return clean if clean else fallback


def find_numeric_value(row: dict[str, str], aliases: list[str]) -> float | None:
    alias_set = {slugify(alias) for alias in aliases}
    for key, value in row.items():
        if slugify(key) not in alias_set:
            continue
        match = NUMERIC_PATTERN.search(value.replace(",", ""))
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def extract_summary_total(fields: list[FieldItem], page_no: int) -> float | None:
    summary_keys = {"total", "grand_total", "amount_due", "合计", "总金额"}
    for field in fields:
        if field.page_no != page_no:
            continue
        if slugify(field.field_key) in {slugify(item) for item in summary_keys}:
            match = NUMERIC_PATTERN.search(field.field_value.replace(",", ""))
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return None
    return None


def polygon_to_bbox(box: list[list[float]]) -> list[float]:
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return [min(xs), min(ys), max(xs), max(ys)]


def bbox_center_x(bbox: list[float]) -> float:
    return (bbox[0] + bbox[2]) / 2


def bbox_center_y(bbox: list[float]) -> float:
    return (bbox[1] + bbox[3]) / 2


def normalize_table_header(value: str, index: int) -> str:
    cleaned = " ".join(value.split()).strip()
    return cleaned or f"column_{index + 1}"


def derive_columns_from_header_rows(rows: list[list[OCRDetection]]) -> tuple[list[str], list[tuple[float, float]]]:
    clusters: list[dict[str, object]] = []

    for row in rows:
        for cell in row:
            text = normalize_header_text(cell.text)
            if not text:
                continue
            center_x = bbox_center_x(cell.bbox)
            matched = None
            for cluster in clusters:
                left, right = cluster["range"]  # type: ignore[misc]
                if left - 24 <= center_x <= right + 24:
                    matched = cluster
                    break
            if matched is None:
                clusters.append({"range": [cell.bbox[0], cell.bbox[2]], "items": [(cell.bbox[1], text)]})
            else:
                matched["range"][0] = min(matched["range"][0], cell.bbox[0])  # type: ignore[index]
                matched["range"][1] = max(matched["range"][1], cell.bbox[2])  # type: ignore[index]
                matched["items"].append((cell.bbox[1], text))  # type: ignore[index]

    clusters.sort(key=lambda cluster: cluster["range"][0])  # type: ignore[index]
    columns: list[str] = []
    ranges: list[tuple[float, float]] = []
    for index, cluster in enumerate(clusters):
        items = [text for _, text in sorted(cluster["items"], key=lambda item: item[0])]  # type: ignore[index]
        header_text = " ".join(items).strip()
        columns.append(normalize_display_header(header_text, index))
        left, right = cluster["range"]  # type: ignore[misc]
        ranges.append((float(left), float(right)))

    if ranges:
        expanded_ranges: list[tuple[float, float]] = []
        centers = [(left + right) / 2 for left, right in ranges]
        for idx, (left, right) in enumerate(ranges):
            previous_boundary = (centers[idx - 1] + centers[idx]) / 2 if idx > 0 else left - 60
            next_boundary = (centers[idx] + centers[idx + 1]) / 2 if idx < len(ranges) - 1 else right + 60
            expanded_ranges.append((previous_boundary, next_boundary))
        ranges = expanded_ranges

    return columns, ranges


def normalize_header_text(value: str) -> str:
    cleaned = " ".join(value.replace('"', "").split()).strip()
    if cleaned in {"€", "e", "v", "w"}:
        return ""
    return cleaned


def normalize_display_header(value: str, index: int) -> str:
    normalized = slugify(value)
    known_headers = {
        "direct_customer": "Direct Customer",
        "direct_custome": "Direct Customer",
        "custome_direct": "Direct Customer",
        "customer_direct": "Direct Customer",
        "team_order": "Team Order #",
        "team_order_": "Team Order #",
        "team_order_#": "Team Order #",
        "order_#": "Team Order #",
        "model": "Model",
        "qty": "Qty",
        "net_revenue": "Net Revenue",
        "单价": "单价",
        "出货时间": "出货时间",
    }
    for key, display in known_headers.items():
        if normalized == slugify(key):
            return display
    return normalize_table_header(value, index)


def looks_like_data_row(row: list[OCRDetection]) -> bool:
    if len(row) < 3:
        return False
    texts = [item.text for item in row]
    has_amount = any(NUMERIC_PATTERN.search(text.replace(",", "")) for text in texts)
    has_model = any(re.search(r"[A-Z]{2,}\d+[A-Z]*", text) for text in texts)
    has_month = any(re.search(r"\d+\s*月", text) for text in texts)
    return has_amount and (has_model or has_month or len(row) >= 5)


def looks_like_continuation_row(row: list[OCRDetection]) -> bool:
    if len(row) < 3:
        return False

    line_text = " ".join(item.text.lower() for item in row)
    if any(token in line_text for token in ("total", "freight", "date de livraison", "complementary")):
        return False

    numeric_cells = sum(1 for item in row if NUMERIC_PATTERN.search(item.text.replace(",", "")))
    has_description = any(re.search(r"[A-Za-zÀ-ÿ]{3,}", item.text) for item in row)
    return numeric_cells >= 2 and has_description


def average_row_gap(row_a: list[OCRDetection], row_b: list[OCRDetection]) -> float:
    row_a_y = sum(bbox_center_y(item.bbox) for item in row_a) / max(len(row_a), 1)
    row_b_y = sum(bbox_center_y(item.bbox) for item in row_b) / max(len(row_b), 1)
    return abs(row_a_y - row_b_y)


def locate_column_index(column_ranges: list[tuple[float, float]], center_x: float) -> int:
    for idx, (left, right) in enumerate(column_ranges):
        if left <= center_x <= right:
            return idx
    return min(range(len(column_ranges)), key=lambda idx: abs(((column_ranges[idx][0] + column_ranges[idx][1]) / 2) - center_x))


def clean_table_cell_value(value: str, column: str) -> str:
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return ""

    if slugify(column) in {"code_produit", "product_code"}:
        return MODEL_CODE_CORRECTIONS.get(cleaned, cleaned)

    if column in {"Net Revenue", "单价"}:
        cleaned = cleaned.replace("€", "").replace(" e ", " ").replace(" e", "").replace("e ", "").strip()
        if re.search(r"\d", cleaned):
            return f"€ {cleaned}"
        return cleaned

    if column == "Qty":
        match = NUMERIC_PATTERN.search(cleaned.replace(",", ""))
        return match.group(0) if match else cleaned

    if column == "出货时间":
        match = re.search(r"(\d+)\s*月", cleaned)
        return f"{match.group(1)}月" if match else cleaned

    return cleaned


def postprocess_table_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    for row in rows:
        code_key = find_column_key(row, ("code produit", "product_code", "model"))
        description_key = find_column_key(row, ("designation", "description"))
        if code_key and row.get(code_key):
            row[code_key] = MODEL_CODE_CORRECTIONS.get(row[code_key], row[code_key])
        if description_key:
            row[description_key] = clean_description_value(row.get(description_key, ""), row.get(code_key, "") if code_key else "")

        qty_key = find_column_key(row, ("qty", "quantity", "数量"))
        unit_key = find_column_key(row, ("p.u.net", "p.u net", "pu net", "unit_price", "price", "单价"))
        amount_key = find_column_key(row, ("montant net", "amount", "net revenue", "金额"))
        if not qty_key or not unit_key or not amount_key:
            continue

        qty = parse_decimal(row.get(qty_key, ""))
        unit_price = parse_decimal(row.get(unit_key, ""))
        amount = parse_decimal(row.get(amount_key, ""))
        qty_is_unusable = qty is None or qty > 10000
        if qty_is_unusable and unit_price and amount:
            inferred_qty = amount / unit_price
            if 0 < inferred_qty < 10000 and abs(inferred_qty - round(inferred_qty)) < 0.05:
                row[qty_key] = str(int(round(inferred_qty)))
                qty = float(round(inferred_qty))

        expected_amount = qty * unit_price if qty is not None and unit_price is not None else None
        amount_is_unusable = amount is None or (
            expected_amount is not None and expected_amount > 0 and amount < expected_amount * 0.1
        )
        if amount_is_unusable and expected_amount is not None and expected_amount > 0:
            row[amount_key] = format_decimal_value(expected_amount)
    return rows


def clean_description_value(value: str, code: str) -> str:
    cleaned = " ".join(value.split()).strip()
    replacements = {
        "TMGSN": "TM65N",
        "TMG5N": "TM65N",
        "TM8SN": "TM85N",
        "TE5ON": "TE50N",
        "TE5SN": "TE55N",
        "TESSN": "TE55N",
        "TEGSN": "TE65N",
    }
    for bad_value, good_value in replacements.items():
        cleaned = cleaned.replace(bad_value, good_value)

    if code == "TM65N" and "MoniteurG5" in cleaned:
        cleaned = cleaned.replace("MoniteurG5", "Moniteur 65")
    if code == "TE65N" and "Moniteur G5" in cleaned:
        cleaned = cleaned.replace("Moniteur G5", "Moniteur 65")
    return cleaned


def find_column_key(row: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    alias_slugs = {slugify(alias) for alias in aliases}
    for key in row:
        key_slug = slugify(key)
        if key_slug in alias_slugs or any(alias_slug in key_slug for alias_slug in alias_slugs):
            return key
    return None


def parse_decimal(value: str) -> float | None:
    cleaned = value.replace("€", "").replace(" ", "").replace("'", "").strip()
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    match = NUMERIC_PATTERN.search(cleaned.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def format_decimal_value(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def row_has_meaningful_values(row: dict[str, str]) -> bool:
    values = [value for value in row.values() if value]
    if len(values) < 3:
        return False
    return any(re.search(r"\d", value) for value in values)


def clamp_confidence(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.9
    return max(0.0, min(1.0, numeric))


def normalize_bbox(value: object) -> list[float]:
    if isinstance(value, list) and len(value) == 4:
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return [0.0, 0.0, 0.0, 0.0]
    return [0.0, 0.0, 0.0, 0.0]


def parse_result_to_json(result: ParseResult) -> str:
    return result.model_dump_json()


def parse_result_from_json(payload: str) -> ParseResult:
    return ParseResult.model_validate(json.loads(payload))


def generate_demo_pdf(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    header_lines = [
        "Invoice No: INV-2026-001",
        "Customer: Acme Trading Co., Ltd.",
        "Date: 2026-04-21",
        "Currency: CNY",
    ]
    y = 72
    for line in header_lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 26

    x_positions = [72, 250, 330, 430, 520]
    y_positions = [220, 260, 300, 340]
    for x in x_positions:
        page.draw_line((x, y_positions[0]), (x, y_positions[-1]), color=(0, 0, 0), width=0.8)
    for y_pos in y_positions:
        page.draw_line((x_positions[0], y_pos), (x_positions[-1], y_pos), color=(0, 0, 0), width=0.8)

    table_rows = [
        ["Item", "Qty", "Unit Price", "Amount"],
        ["Widget A", "2", "100.00", "200.00"],
        ["Widget B", "3", "50.00", "150.00"],
    ]
    for row_index, row in enumerate(table_rows):
        text_y = 245 + row_index * 40
        page.insert_text((86, text_y), row[0], fontsize=11)
        page.insert_text((274, text_y), row[1], fontsize=11)
        page.insert_text((344, text_y), row[2], fontsize=11)
        page.insert_text((444, text_y), row[3], fontsize=11)

    page.insert_text((72, 400), "Total: 350.00", fontsize=13)
    doc.save(output_path)
    doc.close()
    return output_path
