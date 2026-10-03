FROM node:24.18.0-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY backend/src/codestruct/__about__.py /build/backend/src/codestruct/__about__.py
ENV CODESTRUCT_FRONTEND_BASE=/app/
RUN npm run build

FROM python:3.14.6-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CODESTRUCT_DATABASE_PATH=/data/codestruct.sqlite3
WORKDIR /build
COPY pyproject.toml README.md ./
COPY backend/ backend/
COPY --from=frontend /build/frontend/dist/ backend/src/codestruct/web/
RUN python -m pip install --no-cache-dir . && rm -rf /build/*
RUN useradd --create-home --uid 10001 codestruct && mkdir /data /projects && chown codestruct:codestruct /data
USER codestruct
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]
CMD ["codestruct", "serve", "--host", "0.0.0.0", "--port", "8000"]
