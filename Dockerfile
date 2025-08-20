# syntax=docker/dockerfile:1
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer d'abord les deps (meilleur cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code
COPY . .

# Railway/Render fournissent $PORT. En local on publiera 8000:8080.
ENV PORT=8080
CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker -w 3 -b 0.0.0.0:${PORT:-8080} app.main:app"]

