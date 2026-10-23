#!/bin/bash
# Production startup script for Agentic AI Evaluator
# Usage: ./start_production.sh

set -e  # Exit on error

echo "🚀 Starting Agentic AI Evaluator in Production Mode..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file with required environment variables."
    exit 1
fi

# Check if Gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
    echo "📦 Installing Gunicorn..."
    pip install gunicorn
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Set default Gunicorn settings if not provided
export GUNICORN_WORKERS=${GUNICORN_WORKERS:-$(($(nproc) * 2 + 1))}
export GUNICORN_BIND=${GUNICORN_BIND:-"0.0.0.0:8000"}
export GUNICORN_LOG_LEVEL=${GUNICORN_LOG_LEVEL:-"info"}
export GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-"300"}

echo "📊 Configuration:"
echo "   Workers: $GUNICORN_WORKERS"
echo "   Bind: $GUNICORN_BIND"
echo "   Log Level: $GUNICORN_LOG_LEVEL"
echo "   Timeout: $GUNICORN_TIMEOUT seconds"

# Check if Qdrant is accessible
echo "🔍 Checking Qdrant connection..."
if ! curl -s http://localhost:6333/ > /dev/null 2>&1; then
    echo "⚠️  Warning: Qdrant might not be running on localhost:6333"
    echo "   Please ensure Qdrant is started before running the application."
fi

# Check if Redis is accessible
echo "🔍 Checking Redis connection..."
REDIS_HOST=${REDIS_HOST:-"localhost"}
REDIS_PORT=${REDIS_PORT:-"6380"}
if ! redis-cli -h $REDIS_HOST -p $REDIS_PORT ping > /dev/null 2>&1; then
    echo "⚠️  Warning: Redis might not be running on $REDIS_HOST:$REDIS_PORT"
    echo "   Please ensure Redis is started before running the application."
fi

echo ""
echo "✅ Starting Gunicorn server..."
echo ""

# Start Gunicorn
exec gunicorn -c gunicorn_config.py main:app

