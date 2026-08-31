# Build from the repo root: docker build -f serving/Dockerfile -t fraud-serving:latest .
# (needs the repo root as build context so this can COPY the sibling
# feature_store package -- serving reuses fstore.online.RedisOnlineStore
# rather than duplicating the Redis key/serialization logic.)
FROM python:3.11-slim

WORKDIR /app

COPY feature_store/ /app/feature_store/
COPY serving/ /app/serving/
COPY model/ /app/model/

RUN pip install --no-cache-dir -e /app/feature_store -e /app/serving

ENV REDIS_URL=redis://redis:6379/0
ENV MODEL_DIR=/app/model
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "serving.wsgi:app"]
