# UmbraStride API — FastAPI + geo-core + routing-core
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/geo-core /app/packages/geo-core
COPY packages/routing-core /app/packages/routing-core
COPY services/api /app/services/api

RUN pip install --no-cache-dir \
    -e /app/packages/geo-core \
    -e /app/packages/routing-core \
    -e /app/services/api

ENV DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "umbrastride_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
