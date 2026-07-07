FROM node:18-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.10-slim AS base
WORKDIR /app

COPY code-app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY code-app/app ./app
COPY scripts ./scripts

RUN pip install --no-cache-dir torch transformers sentence-transformers optimum optimum-onnx && \
    PYTHONPATH=/app python -c "from app.services.onnx_embeddings import export_onnx; export_onnx()" && \
    pip uninstall -y torch transformers sentence-transformers optimum optimum-onnx && \
    pip cache purge

COPY --from=frontend /build/build /frontend/build

ENV PYTHONPATH=/app
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
