# Multi-stage build not needed for Python approach.
# fastmemory is distributed as a pre-compiled PyO3 wheel (no Rust toolchain required).
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and data
COPY app.py atf_parser.py ./
COPY data/ ./data/

# Render.com exposes port 10000 by default; honour $PORT env var at runtime
EXPOSE 10000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
