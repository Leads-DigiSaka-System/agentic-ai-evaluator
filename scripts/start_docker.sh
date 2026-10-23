#!/bin/bash
# Quick start script for Docker deployment
# Usage: ./start_docker.sh [dev|prod]

MODE=${1:-prod}

if [ "$MODE" == "dev" ]; then
    echo "🚀 Starting in DEVELOPMENT mode (with hot reload)..."
    docker compose -f docker/docker-compose.dev.yml up -d --build
    echo ""
    echo "✅ Services started in development mode"
    echo "📊 View logs: docker compose -f docker/docker-compose.dev.yml logs -f"
else
    echo "🚀 Starting in PRODUCTION mode..."
    docker compose -f docker/docker-compose.yml up -d --build
    echo ""
    echo "✅ Services started in production mode"
    echo "📊 View logs: docker compose -f docker/docker-compose.yml logs -f"
fi

echo ""
echo "🌐 FastAPI: http://localhost:8000"
echo "📊 Qdrant Dashboard: http://localhost:6333/dashboard"
echo "🔍 Health Check: http://localhost:8000/api/health"

