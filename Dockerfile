# syntax=docker/dockerfile:1
# ── All-in-one image (frontend + backend + PostgreSQL) ──────────────────
# Works on Linux, Windows (Docker Desktop/WSL2), and macOS.
# On Windows: clone the repo inside WSL2 for best volume-mount performance.

# ── Stage 1: build Vue/Vite frontend ────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY src/frontend/package*.json ./
RUN npm install

COPY src/frontend ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ── Stage 2: Python app + embedded PostgreSQL ───────────────────────────
FROM python:3.11-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POSTGRES_USER=ueba_user
ENV POSTGRES_PASSWORD=ueba_password
ENV POSTGRES_DB=ueba_db
ENV POSTGRES_HOST=127.0.0.1
ENV POSTGRES_PORT=5432
ENV DATABASE_URL=postgresql://ueba_user:ueba_password@127.0.0.1:5432/ueba_db
ENV FRONTEND_DIST_DIR=/app/src/frontend/dist
ENV OCSVM_MODEL_PATH=/app/src/ml/weights/ocsvm_cert_r42_chunked.joblib
ENV ML_MODEL_PATH=/app/src/ml/weights
ENV ML_ARTIFACT_PATH=/app/artifacts
ENV CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql postgresql-contrib curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY --from=frontend-builder /frontend/dist ./src/frontend/dist

# Entrypoint script — strip Windows CR characters so the script runs even
# when the repo was checked out with CRLF on a Windows host.
# Using 'tr -d' (POSIX) instead of 'sed' because GNU sed vs BSD sed behave
# differently with \r, and busybox sed (Alpine) may not support it at all.
COPY scripts/docker/all_in_one_entrypoint.sh /usr/local/bin/all_in_one_entrypoint.sh
RUN tr -d '\r' < /usr/local/bin/all_in_one_entrypoint.sh > /tmp/entrypoint_clean \
    && mv /tmp/entrypoint_clean /usr/local/bin/all_in_one_entrypoint.sh \
    && chmod +x /usr/local/bin/all_in_one_entrypoint.sh \
    && echo "[dockerfile] entrypoint CRLF check: $(file /usr/local/bin/all_in_one_entrypoint.sh)"

EXPOSE 8000 5432

CMD ["/usr/local/bin/all_in_one_entrypoint.sh"]
