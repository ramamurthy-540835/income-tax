FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser itr_backend ./itr_backend
COPY --chown=appuser:appuser itr_agent/schemas ./itr_agent/schemas

USER appuser

CMD ["sh", "-c", "exec uvicorn itr_backend.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
