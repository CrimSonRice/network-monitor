# Multi-stage build: smaller image, no dev deps in prod
# Target: Linux production (Windows dev uses venv + uvicorn directly)

# ---- Builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip wheel --no-deps -w /wheels -r requirements.txt

# ---- Runtime ----
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

COPY --chown=app:app . .

USER app

EXPOSE 8000

# Uvicorn; use GUNICORN_CMD_ARGS in prod if you switch to gunicorn+uvicorn workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
