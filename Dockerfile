FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHECKPOINT_DB_PATH=/app/state/checkpoints.sqlite

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent_graph.py api.py mcp_server.py vector_search.py ./
COPY embed_chunks.py ingest_documents.py ./

RUN mkdir -p /app/data /app/state

VOLUME ["/app/state"]

EXPOSE 8000

CMD ["sh", "-c", "python ingest_documents.py && python embed_chunks.py && exec uvicorn api:app --host 0.0.0.0 --port 8000"]
