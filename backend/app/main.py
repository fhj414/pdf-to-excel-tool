from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, engine
from app.logging_config import configure_logging
from app.routers.documents import router as documents_router

settings = get_settings()
configure_logging(settings.log_level)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PDF to Excel Tool", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")

