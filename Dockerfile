# ---------- build stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- runtime stage ----------
FROM python:3.12-slim

LABEL maintainer="J9 Project"

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

COPY --from=builder /install /usr/local

COPY api/ api/
COPY core/ core/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

USER app

CMD ["sh", "-c", "gunicorn api.main:app --worker-class uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:${PORT:-8080} --timeout 120 --keep-alive 5 --access-logfile - --error-logfile -"]
