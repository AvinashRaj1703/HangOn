# Enterprise Government & Police Intranet Deployment Container
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose HTTP and WebSocket port
EXPOSE 8000

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Healthcheck for government container orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Launch production server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
