from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FieldItem(BaseModel):
    field_key: str
    field_value: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[float] = Field(default_factory=lambda: [0, 0, 0, 0], min_length=4, max_length=4)
    page_no: int = Field(ge=1)
    source_type: Literal["text", "table", "ocr", "rule"]


class TableItem(BaseModel):
    columns: list[str]
    rows: list[dict[str, str]]
    page_no: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ValidationIssue(BaseModel):
    rule: str
    message: str
    severity: Literal["warning", "error"]
    page_no: int | None = None
    field_key: str | None = None
    table_row: int | None = None


class PagePreview(BaseModel):
    page_no: int
    image_url: str
    width: float
    height: float


class ParseStats(BaseModel):
    field_count: int
    table_count: int
    low_confidence_count: int
    error_count: int


class ParseResult(BaseModel):
    pdf_type: Literal["digital", "scanned"]
    fields: list[FieldItem]
    tables: list[TableItem]
    validation_issues: list[ValidationIssue]
    pages: list[PagePreview]
    stats: ParseStats


class DocumentResponse(BaseModel):
    id: int
    filename: str
    pdf_type: str
    page_count: int
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    parse_result: ParseResult

    model_config = {"from_attributes": True}


class DocumentSummary(BaseModel):
    id: int
    filename: str
    pdf_type: str
    page_count: int
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FieldUpdateRequest(BaseModel):
    field_value: str


class UploadResponse(BaseModel):
    document_id: int
    status: str

