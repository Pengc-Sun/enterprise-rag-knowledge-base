FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md alembic.ini ./
COPY backend ./backend
COPY migrations ./migrations

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && mkdir -p /app/storage/uploads \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
