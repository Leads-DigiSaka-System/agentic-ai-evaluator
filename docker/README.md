# Docker Deployment Guide

## 🐳 Complete Docker Setup

This setup includes:
- ✅ FastAPI Application (Gunicorn)
- ✅ ARQ Worker (Background Jobs)
- ✅ Redis (Job Queue & Cache)
- ⚠️ **Qdrant is EXTERNAL** - Configure `Qdrant_Localhost` in `.env` to point to your Qdrant instance

---

## 🚀 Quick Start

### 1. Build and Start All Services

```bash
cd C:\Users\Crich Joved\OneDrive\Desktop\agentic-ai-evaluator
docker compose -f docker/docker-compose.yml up -d --build
```

### 2. Check Status

```bash
docker compose -f docker/docker-compose.yml ps
```

### 3. View Logs

```bash
# All services
docker compose -f docker/docker-compose.yml logs -f

# Specific service
docker compose -f docker/docker-compose.yml logs -f fastapi
docker compose -f docker/docker-compose.yml logs -f worker
docker compose -f docker/docker-compose.yml logs -f redis
docker compose -f docker/docker-compose.yml logs -f qdrant
```

---

## 📋 Services

### FastAPI (Port 8000)
- Main API server
- Handles HTTP requests
- Enqueues background jobs

**Access:**
- API: http://localhost:8000
- Health: http://localhost:8000/api/health
- Docs: http://localhost:8000/docs

### ARQ Worker
- Processes background jobs
- Listens to Redis queue
- Updates job progress

**Logs:**
```bash
docker compose -f docker/docker-compose.yml logs -f worker
```

### Redis (Port 6380)
- Job queue storage
- Cache storage
- Progress tracking

**Access:**
```bash
docker exec -it agentic_redis redis-cli
```

### Qdrant (External)
- Vector database (separate instance)
- Stores embeddings
- Analysis storage
- **Configure in `.env`**: `Qdrant_Localhost=http://your-qdrant-host:6333`

---

## 🔧 Configuration

### Environment Variables

Create `.env` file in project root:

```env
# API Configuration
API_KEY=your-api-key-here
GEMINI_APIKEY=your-gemini-key
GEMINI_MODEL=gemini-1.5-flash

# Qdrant (external instance - set your Qdrant URL here)
Qdrant_Localhost=http://your-qdrant-host:6333
Qdrant_Form=your_collection
Qdrant_Analysis_Report=your_analysis_collection

# Redis (will be overridden by docker-compose)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Other settings
EMBEDDING_MODEL=your-model
CONNECTION_WEB=http://localhost:8501
```

---

## 🛠️ Common Commands

### Start Services
```bash
docker compose -f docker/docker-compose.yml up -d
```

### Stop Services
```bash
docker compose -f docker/docker-compose.yml down
```

### Restart Service
```bash
docker compose -f docker/docker-compose.yml restart fastapi
docker compose -f docker/docker-compose.yml restart worker
```

### Rebuild After Code Changes
```bash
docker compose -f docker/docker-compose.yml up -d --build
```

### View Logs
```bash
# All services
docker compose -f docker/docker-compose.yml logs -f

# Specific service
docker compose -f docker/docker-compose.yml logs -f fastapi
```

### Execute Commands in Container
```bash
# FastAPI container
docker exec -it agentic_fastapi bash

# Worker container
docker exec -it agentic_worker bash

# Redis CLI
docker exec -it agentic_redis redis-cli
```

### Scale Workers (Run Multiple Worker Instances)
```bash
docker compose -f docker/docker-compose.yml up -d --scale worker=3
```

---

## 📊 Monitoring

### Check Service Health
```bash
# FastAPI health
curl http://localhost:8000/api/health

# Worker health (requires API key)
curl -H "X-API-Key: your-key" http://localhost:8000/api/worker/health

# Redis
docker exec -it agentic_redis redis-cli ping

# Qdrant
curl http://localhost:6333/
```

### View Resource Usage
```bash
docker stats
```

---

## 🐛 Troubleshooting

### Service Won't Start
```bash
# Check logs
docker compose -f docker/docker-compose.yml logs

# Check service status
docker compose -f docker/docker-compose.yml ps
```

### Rebuild Everything
```bash
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml build --no-cache
docker compose -f docker/docker-compose.yml up -d
```

### Clear Redis Data
```bash
docker compose -f docker/docker-compose.yml down
docker volume rm agentic-ai-evaluator_redis_data
docker compose -f docker/docker-compose.yml up -d
```

### Qdrant is External
Qdrant is not managed by this Docker Compose setup. Manage your Qdrant instance separately.

---

## 🚀 Production Deployment

### 1. Remove Development Volumes
In `docker-compose.yml`, remove or comment out volume mounts for code:
```yaml
# Remove these lines in production:
volumes:
  - ../src:/app/src:ro
```

### 2. Use Production Environment
```bash
# Set production environment variables
export ENV=production
```

### 3. Use Docker Secrets (Recommended)
Instead of `.env` file, use Docker secrets for sensitive data.

### 4. Enable Resource Limits
Add to each service in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

---

## ✅ Verification

After starting, verify all services:

1. **FastAPI**: http://localhost:8000/api/health
2. **Qdrant**: Verify your external Qdrant instance is accessible
3. **Redis**: `docker exec -it agentic_redis redis-cli ping`
4. **Worker**: Check logs for "Starting ARQ worker"

---

## 📝 Notes

- All services are on the same Docker network (`app_network`)
- Services communicate using service names (redis, fastapi, worker)
- **Qdrant is external** - configure the URL in `.env` file
- Ports are exposed to host for external access
- Data is persisted in Docker volumes (Redis only)
- Health checks ensure services start in correct order

---

**Ready for deployment!** 🎉

