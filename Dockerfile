# Dependency resolution needs internet while building. Runtime uses local files.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS backend-build
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app/backend
RUN python -m pip install --no-cache-dir uv==0.11.16
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/backend/.venv/bin:$PATH" \
    DATABASE_URL=sqlite:////app/backend/var/dds.db \
    BACKUP_DIR=/app/backend/var/backups \
    STATIC_DIR=/app/frontend/dist \
    AI_MODE=rules AI_ENDPOINT="" SPEECH_ENDPOINT="" TTS_ENDPOINT=""
RUN groupadd --gid 10001 dds && useradd --uid 10001 --gid dds --no-create-home dds
WORKDIR /app/backend
COPY --from=backend-build /app/backend/.venv /app/backend/.venv
COPY backend/app ./app
COPY backend/data ./data
COPY scripts/backup.py scripts/restore.py /app/scripts/
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
COPY docs/third-party-notices.md /app/licenses/frontend-third-party-notices.md
RUN mkdir -p /app/backend/var/backups && chown -R dds:dds /app/backend/var
USER dds
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
