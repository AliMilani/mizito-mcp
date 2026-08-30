FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir "fastmcp" "httpx[socks]"

COPY server.py .

# Token is injected at runtime, never baked into the image:
#   docker run --rm -i --env-file .env mizito-mcp
ENV MIZITO_BASE=https://app.mizito.ir

ENTRYPOINT ["python", "server.py"]
