FROM python:3.11-slim AS backend-base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY .env.example /app/.env.example

EXPOSE 8000

# Render provides $PORT. Locally it falls back to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

FROM node:20-alpine AS frontend-base

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* /app/frontend/
RUN npm i -g npm@11.12.1 && npm ci --no-audit --no-fund

COPY frontend /app/frontend

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

