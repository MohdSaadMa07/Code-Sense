FROM node:18-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY code-app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip cache purge
COPY code-app/app ./app

COPY --from=frontend /build/build /frontend/build

ENV PYTHONPATH=/app
EXPOSE 7860
RUN python -c "from app.main import app; print('Import OK')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --log-level debug"]
