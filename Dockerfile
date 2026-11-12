FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY mizito_mcp ./mizito_mcp

# Token is injected at runtime, never baked into the image:
#   docker run --rm -i --env-file .env mizito-mcp
# Add MIZITO_READ_ONLY=1 to the env file for a server with no write tools.
ENV MIZITO_BASE=https://app.mizito.ir

ENTRYPOINT ["python", "server.py"]
