#!/bin/sh
# Fail on error
set -e

# Default to port 8080 if not set
PORT="${PORT:-8080}"

echo "Starting RAMA AI Backend on port $PORT..."
exec uvicorn app:app --host 0.0.0.0 --port "$PORT"

