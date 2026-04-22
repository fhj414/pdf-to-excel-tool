import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import Document
from app.schemas import DocumentResponse, FieldUpdateRequest, UploadResponse, ValidationIssue
from app.services.excel_exporter import export_excel
from app.services.pdf_parser import (
    empty_parse_result,
    ensure_pdf_input,
    generate_demo_pdf,
    parse_pdf,
    parse_result_from_json,
    parse_result_to_json,
    validate_fields,
)

router = APIRouter(tags=["documents"])
logger = logging.getLogger(__name__)
settings = get_settings()
executor = ThreadPoolExecutor(max_workers=2)


def get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def process_document_in_background(document_id: int) -> None:
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if not document:
            logger.warning("Background parse skipped; document %s not found", document_id)
            return

        parse_input_path = ensure_pdf_input(Path(document.original_path))
        result = parse_pdf(parse_input_path, settings.static_path, settings.export_path, document.id)
        document.pdf_type = result.pdf_type
        document.page_count = len(result.pages)
        document.status = "processed"
        document.parse_result = parse_result_to_json(result)
        db.add(document)
        db.commit()
    except Exception as exc:
        logger.exception("Background parse failed for document %s", document_id)
        document = db.get(Document, document_id)
        if document:
            result = empty_parse_result()
            result.validation_issues.append(
                ValidationIssue(rule="parse_failed", message=str(exc), severity="error")
            )
            result.stats.error_count = 1
            document.status = "failed"
            document.parse_result = parse_result_to_json(result)
            db.add(document)
            db.commit()
    finally:
        db.close()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    filename = file.filename or "upload.bin"
    file_suffix = Path(filename).suffix.lower()
    allowed_suffixes = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    if file_suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="Only PDF and common image files are supported")

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_upload_mb} MB limit")

    stored_name = f"{uuid4().hex}_{filename}"
    stored_path = settings.upload_path / stored_name
    stored_path.write_bytes(content)

    document = Document(filename=filename, original_path=str(stored_path), status="processing")
    db.add(document)
    db.commit()
    db.refresh(document)

    executor.submit(process_document_in_background, document.id)
    return UploadResponse(document_id=document.id, status=document.status)


@router.post("/demo/generate", response_model=UploadResponse)
def generate_demo_document(db: Session = Depends(get_db)) -> UploadResponse:
    demo_path = settings.upload_path / f"demo_{uuid4().hex[:8]}.pdf"
    generate_demo_pdf(demo_path)

    document = Document(filename="demo_invoice.pdf", original_path=str(demo_path), status="processing")
    db.add(document)
    db.commit()
    db.refresh(document)

    executor.submit(process_document_in_background, document.id)
    return UploadResponse(document_id=document.id, status=document.status)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentResponse:
    document = get_document_or_404(db, document_id)
    parse_result = parse_result_from_json(document.parse_result)
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        pdf_type=document.pdf_type,
        page_count=document.page_count,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        parse_result=parse_result,
    )


@router.put("/documents/{document_id}/fields/{field_index}", response_model=DocumentResponse)
def update_field(
    document_id: int,
    field_index: int,
    payload: FieldUpdateRequest,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = get_document_or_404(db, document_id)
    result = parse_result_from_json(document.parse_result)

    if field_index < 0 or field_index >= len(result.fields):
        raise HTTPException(status_code=404, detail="Field not found")

    result.fields[field_index].field_value = payload.field_value
    result.validation_issues = validate_fields(result.fields, result.tables)
    result.stats.low_confidence_count = sum(1 for field in result.fields if field.confidence < 0.75)
    result.stats.error_count = sum(1 for issue in result.validation_issues if issue.severity == "error")
    document.parse_result = parse_result_to_json(result)
    db.add(document)
    db.commit()
    db.refresh(document)

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        pdf_type=document.pdf_type,
        page_count=document.page_count,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        parse_result=result,
    )


@router.get("/documents/{document_id}/export")
def download_excel(document_id: int, db: Session = Depends(get_db)) -> FileResponse:
    document = get_document_or_404(db, document_id)
    result = parse_result_from_json(document.parse_result)
    export_path = settings.export_path / f"document_{document.id}_export.xlsx"
    export_excel(result, export_path)
    return FileResponse(
        path=export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{Path(document.filename).stem}.xlsx",
    )
