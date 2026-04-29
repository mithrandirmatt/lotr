# ============================================================
# LotR TCG MCP Server
# Provides filesystem, git, shell, and postgres tools via SSE.
#
# Build (from repo root):
#   docker build -t lotr-mcp build/docker/mcp/
# Run standalone:
#   docker run --rm -p 3100:3100 -v "$(pwd):/workspace" lotr-mcp
# ============================================================

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV WORKSPACE=/workspace \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=3100

EXPOSE 3100

CMD ["python", "server.py"]
