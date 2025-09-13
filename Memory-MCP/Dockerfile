# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEM_TOKEN= \
    MEM_HOME=/data/memorydb

WORKDIR /app

# Install runtime deps and build Memory-MCP package
COPY pyproject.toml ./
COPY server ./server
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 7090
VOLUME ["/data"]

CMD ["memory-mcp", "--home", "/data/memorydb", "--host", "0.0.0.0", "--port", "7090"]

