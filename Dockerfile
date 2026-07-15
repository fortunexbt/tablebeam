FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OLLAMA_HOST=http://host.docker.internal:11434 \
    VECTOR_DB_PATH=/data/chroma_db_clients

WORKDIR /app

COPY src/requirements.txt /app/src/requirements.txt
RUN python -m pip install --upgrade pip --disable-pip-version-check \
    && python -m pip install -r /app/src/requirements.txt --disable-pip-version-check

COPY src/ /app/src/
COPY sample_data.csv README.md /app/

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data/chroma_db_clients \
    && chown -R appuser:appuser /app /data

USER appuser
EXPOSE 8501

CMD ["streamlit", "run", "src/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
