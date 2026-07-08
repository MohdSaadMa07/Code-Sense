#!/bin/sh
set -e
echo "=== STARTUP DEBUG ==="
echo "Python: $(python --version 2>&1)"
echo "PYTHONPATH: $PYTHONPATH"
echo "PORT: ${PORT:-7860}"
echo "Testing import..."
python -c "from app.main import app; print('Import OK')" 2>&1
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --log-level debug
