FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install the neuro-onto-gen package
COPY . /app
RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -e ".[llm,clustering,owl]" || true

# CLI tool — keep alive as a long-running container
CMD ["tail", "-f", "/dev/null"]
