
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Application code
COPY backend/ /app/backend/

# Database migrations and configuration
COPY database/ /app/database/
COPY alembic.ini /app/alembic.ini

# ML model and prediction code
COPY ml/ /app/ml/

# Evidence directory; actual uploaded files go on persistent storage
RUN mkdir -p /app/storage/evidence

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
