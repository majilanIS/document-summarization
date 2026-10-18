# syntax=docker/dockerfile:1
# FastAPI back-end.
#
#   docker build -t docs-summarizer-api .
#   docker run -d -p 8000:8000 --env-file .env -v docs-data:/app/data docs-summarizer-api
#
# By default the image uses Gemini only (set GEMINI_API_KEY) and stays small.
# To include the offline Hugging Face models as well (CPU build of torch,
# a much larger image):
#
#   docker build --build-arg WITH_LOCAL_MODELS=true -t docs-summarizer-api .

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so code changes don't reinstall them. The pip cache
# lives in a BuildKit cache mount: rebuilds reuse downloads, and none of it
# ends up in the image.
ARG WITH_LOCAL_MODELS=false
COPY requirements.txt requirements-server.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$WITH_LOCAL_MODELS" = "true" ]; then \
        pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt; \
    else \
        pip install -r requirements-server.txt; \
    fi

COPY app ./app

# Run as a non-root user. /app/data holds the SQLite database and, with
# local models, the downloaded model files; mount a volume there to keep them.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data \
    && chown app:app /app/data
USER app

ENV DATABASE_PATH=/app/data/app.db \
    HF_HOME=/app/data/huggingface \
    PORT=8000

VOLUME /app/data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"

# One worker on purpose: SQLite and the in-memory reward model are shared
# state, and slow model calls already run in FastAPI's thread pool.
# PORT can be set by the host (Render, Railway, Cloud Run, ...).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
