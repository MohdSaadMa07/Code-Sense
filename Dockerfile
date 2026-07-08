FROM python:3.12-slim
WORKDIR /app

COPY code-app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip cache purge
COPY code-app/app ./app

ENV PYTHONPATH=/app
EXPOSE 7860
RUN python -c "from app.main import app; print('Import OK')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --log-level debug"]
