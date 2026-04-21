import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pdf_to_excel_app.db")
os.environ.setdefault("UPLOAD_DIR", "/tmp/pdf_to_excel_uploads")
os.environ.setdefault("EXPORT_DIR", "/tmp/pdf_to_excel_exports")
os.environ.setdefault("STATIC_DIR", "/tmp/pdf_to_excel_static")
os.environ.setdefault(
    "CORS_ORIGINS_RAW",
    "https://pdf-to-excel-tool.vercel.app,http://localhost:3000,http://127.0.0.1:3000",
)

from app.config import get_settings  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.routers.documents import router as documents_router  # noqa: E402

settings = get_settings()
configure_logging(settings.log_level)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PDF to Excel Tool API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vercel Services strips the /api routePrefix before forwarding here.
app.include_router(documents_router)
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")

