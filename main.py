import os
import signal
import atexit
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes.upload import router as upload_router
from src.api.routes.search import router as search_router
from src.api.routes.delete_extract import router as delete_router
from src.api.routes.agent import router as agent_router
from src.api.routes.storage import router as storage_router
from src.api.routes.progress import router as progress_router
from src.api.routes.cache import router as cache_router
from src.api.routes.worker import router as worker_router
from src.api.routes.list import router as list_router
from src.api.routes.chat_router import router as chat_router
from src.api.deps.security import require_api_key
from dotenv import load_dotenv
from datetime import datetime
from src.core.config import CORS_ORIGINS, ENVIRONMENT, RATE_LIMIT_ENABLED
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from src.shared.logging.safe_logger import SafeLogger
from src.shared.logging.simple_clean_logging import setup_clean_logging, get_clean_logger
from slowapi.middleware import SlowAPIMiddleware
from src.shared.limiter_config import limiter    

# Load .env
load_dotenv()

# Setup clean logging with colors
setup_clean_logging("INFO")
logger = get_clean_logger(__name__)

# CRITICAL: Initialize Langfuse v3 BEFORE importing routes
# This ensures Langfuse is ready when nodes are imported
try:
    from src.monitoring.trace.langfuse_helper import initialize_langfuse
    if initialize_langfuse():
        logger.info("Langfuse v3 initialized successfully")
    else:
        logger.info("ℹLangfuse not configured or initialization skipped")
except Exception as e:
    logger.warning(f"Langfuse initialization failed: {e}")
    logger.info("ℹContinuing without Langfuse observability")

# Setup PostgreSQL conversation memory (if configured)
try:
    from src.infrastructure.postgres.postgres_memory_schema import setup_postgres_memory
    if setup_postgres_memory():
        logger.info("✅ PostgreSQL conversation memory ready (production mode)")
    else:
        logger.info("ℹ️ Using in-memory conversation memory (development mode)")
except Exception as e:
    logger.warning(f"⚠️ PostgreSQL memory setup skipped: {e}")
    logger.info("ℹ️ Using in-memory conversation memory (development mode)")

# Graceful shutdown handler
def shutdown_handler():
    """Handle graceful shutdown"""
    logger.info("Shutting down gracefully...")
    logger.info("Closing database connections...")
    
    # Close shared Redis pool (sync version for atexit)
    try:
        import asyncio
        from src.infrastructure.redis.redis_pool import close_shared_redis_pool
        # Try to close if event loop exists
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, schedule the close
                asyncio.create_task(close_shared_redis_pool())
            else:
                loop.run_until_complete(close_shared_redis_pool())
        except RuntimeError:
            # No event loop, skip
            pass
        logger.info("Shared Redis pool closed on shutdown")
    except Exception as e:
        logger.debug(f"Redis pool shutdown error (non-critical): {e}")
    
    # Flush and shutdown Langfuse
    try:
        from src.monitoring.trace.langfuse_helper import flush_langfuse, shutdown_langfuse
        flush_langfuse()
        shutdown_langfuse()
        logger.info("Langfuse flushed and shutdown")
    except Exception as e:
        logger.debug(f"Langfuse shutdown error (non-critical): {e}")
    
    logger.info("Shutdown complete")

# Register shutdown handlers
atexit.register(shutdown_handler)

def signal_handler(sig, frame):
    """Handle SIGINT and SIGTERM"""
    logger.info(f"Received signal {sig}, initiating shutdown...")
    shutdown_handler()
    os._exit(0)

# Register signal handlers (Unix/Linux only - Windows doesn't support SIGTERM)
# These work fine in Docker (Linux) and when using Gunicorn/Uvicorn
if hasattr(signal, 'SIGINT'):
    signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, signal_handler)

app = FastAPI()

# Add FastAPI shutdown event for cleanup
@app.on_event("startup")
async def startup_event():
    """FastAPI startup event - initialize services and cleanup"""
    logger.info("Application starting up...")
    
    # Validate configuration first (fail fast if critical configs are missing)
    try:
        from src.core.config import validate_and_log_config
        validate_and_log_config()
    except ValueError as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        logger.error("Application cannot start without required configuration.")
        raise
    
    # Initialize PostgreSQL connection pool (if PostgreSQL is configured)
    try:
        from src.infrastructure.postgres.postgres_pool import get_postgres_pool
        pool = get_postgres_pool()
        if pool:
            logger.info("✅ PostgreSQL connection pool ready")
    except Exception as e:
        logger.warning(f"PostgreSQL pool initialization failed (non-critical): {e}")
    
    # Clean up expired cache entries on startup
    try:
        from src.services.cache_service import agent_cache
        cleaned_count = await agent_cache.cleanup_expired_caches()
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired cache entries on startup")
        else:
            logger.info("No expired cache entries to clean up")
    except Exception as e:
        logger.warning(f"Cache cleanup on startup failed (non-critical): {e}")
    
    logger.info("✅ Startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event - cleanup resources before shutdown"""
    logger.info("Application shutting down...")
    
    # Close PostgreSQL connection pool
    try:
        from src.infrastructure.postgres.postgres_pool import close_pool
        close_pool()
    except Exception as e:
        logger.debug(f"PostgreSQL pool cleanup failed (non-critical): {e}")
    
    # Clean up expired cache entries on shutdown
    try:
        from src.services.cache_service import agent_cache
        cleaned_count = await agent_cache.cleanup_expired_caches()
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} expired cache entries on shutdown")
    except Exception as e:
        logger.debug(f"Cache cleanup on shutdown failed (non-critical): {e}")
    
    # Close shared Redis pool
    try:
        from src.infrastructure.redis.redis_pool import close_shared_redis_pool
        await close_shared_redis_pool()
        logger.info("Shared Redis pool closed on FastAPI shutdown")
    except Exception as e:
        logger.debug(f"Redis pool shutdown error (non-critical): {e}")
    
    # Flush Langfuse
    try:
        from src.monitoring.trace.langfuse_helper import flush_langfuse, shutdown_langfuse
        flush_langfuse()
        shutdown_langfuse()
        logger.info("Langfuse flushed on FastAPI shutdown")
    except Exception as e:
        logger.debug(f"Langfuse shutdown error (non-critical): {e}")
    
    logger.info("Shutdown complete")


app.state.limiter = limiter
if RATE_LIMIT_ENABLED:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
# Initialize FastAPI app
# CORS: production = restrict to CORS_ORIGINS; development/staging = allow all
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if ENVIRONMENT == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Secure all API routes with API key. Health and admin validate can remain open if desired.
app.include_router(upload_router, prefix="/api", tags=["Upload"], dependencies=[Depends(require_api_key)])
app.include_router(agent_router, prefix="/api", tags=["agent"], dependencies=[Depends(require_api_key)])
app.include_router(list_router, prefix="/api", tags=["list"], dependencies=[Depends(require_api_key)]) # Re-enabled with debug
app.include_router(search_router, prefix="/api", tags=["search"], dependencies=[Depends(require_api_key)])
app.include_router(storage_router, prefix="/api", tags=["storage"], dependencies=[Depends(require_api_key)])  # Re-enabled with debug
app.include_router(progress_router, prefix="/api", tags=["progress"], dependencies=[Depends(require_api_key)])

#This router is not open for production for debugging only
app.include_router(cache_router, prefix="/api", tags=["cache"], dependencies=[Depends(require_api_key)])
app.include_router(worker_router, prefix="/api", tags=["worker"], dependencies=[Depends(require_api_key)])
app.include_router(delete_router, prefix="/api", tags=["delete"], dependencies=[Depends(require_api_key)])
app.include_router(chat_router, tags=["chat"], dependencies=[Depends(require_api_key)])  # Prefix already in router

# Health check endpoint
@app.get("/")
def root():
    return {"message": "Agentic AI Evaluation API is running"}

@app.get("/api/health")
def health_check():
    """
    Real health check - verifies database and services
    """
    health_status = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # Check Database (Qdrant)
    try:
        from src.core.config import QDRANT_LOCAL_URI, QDRANT_API_KEY
        from qdrant_client import QdrantClient
        
        if QDRANT_API_KEY:
            client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=10)
        else:
            client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=10)
        
        collections = client.get_collections()
        health_status["checks"]["database"] = {
            "status": "ok",
            "url": QDRANT_LOCAL_URI,
            "collections_count": len(collections.collections)
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["database"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check LLM (Gemini)
    try:
        from src.shared.llm_helper import llm
        health_status["checks"]["llm"] = {"status": "ok"}
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["llm"] = {
            "status": "error",
            "error": str(e)
        }
    
    return health_status

@app.get("/api/qdrant/check")
def check_qdrant_connection():
    """
    Check Qdrant connection status with detailed information
    """
    from src.core.config import QDRANT_LOCAL_URI, QDRANT_API_KEY, QDRANT_COLECTION_DEMO, QDRANT_COLLECTION_ANALYSIS
    from qdrant_client import QdrantClient
    import time
    
    result = {
        "status": "unknown",
        "timestamp": datetime.now().isoformat(),
        "connection": {},
        "collections": {},
        "error": None
    }
    
    try:
        # Test connection
        start_time = time.time()
        
        if QDRANT_API_KEY:
            client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=60)
            auth_method = "API Key"
        else:
            client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=60)
            auth_method = "No Authentication"
        
        # Get Qdrant version/info
        try:
            # Try to get collections as a connection test
            collections_response = client.get_collections()
            connection_time = round((time.time() - start_time) * 1000, 2)  # milliseconds
            
            result["status"] = "connected"
            result["connection"] = {
                "url": QDRANT_LOCAL_URI,
                "auth_method": auth_method,
                "response_time_ms": connection_time,
                "status": "ok"
            }
            
            # Get collection details
            all_collections = []
            for col in collections_response.collections:
                try:
                    col_info = client.get_collection(col.name)
                    all_collections.append({
                        "name": col.name,
                        "points_count": col_info.points_count,
                        "vectors_count": col_info.vectors_count,
                        "status": "ok"
                    })
                except Exception as e:
                    all_collections.append({
                        "name": col.name,
                        "status": "error",
                        "error": str(e)
                    })
            
            result["collections"] = {
                "total": len(collections_response.collections),
                "list": all_collections
            }
            
            # Check specific collections
            expected_collections = {
                "form": QDRANT_COLECTION_DEMO,
                "analysis": QDRANT_COLLECTION_ANALYSIS
            }
            
            collection_status = {}
            for key, collection_name in expected_collections.items():
                try:
                    col_info = client.get_collection(collection_name)
                    collection_status[key] = {
                        "name": collection_name,
                        "exists": True,
                        "points_count": col_info.points_count,
                        "vectors_count": col_info.vectors_count,
                        "status": "ok"
                    }
                except Exception as e:
                    collection_status[key] = {
                        "name": collection_name,
                        "exists": False,
                        "status": "not_found",
                        "error": str(e)
                    }
            
            result["collections"]["expected"] = collection_status
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["connection"] = {
                "url": QDRANT_LOCAL_URI,
                "auth_method": auth_method,
                "status": "failed",
                "error": str(e)
            }
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["connection"] = {
            "url": QDRANT_LOCAL_URI if QDRANT_LOCAL_URI else "not_configured",
            "status": "failed",
            "error": str(e)
        }
    
    return result

@app.get("/api/admin/validate-database")
def validate_database():
    """
    Admin endpoint to validate database integrity
    
    Checks:
    - Total points in database
    - Indexed vectors count
    - Collection health
    - Connection status
    """
    try:
        from src.infrastructure.vector_store.insert import qdrant_client
        
        # Get all collections
        collections_info = []
        try:
            collections = qdrant_client.client.get_collections()
            for collection in collections.collections:
                collection_details = qdrant_client.client.get_collection(collection.name)
                collections_info.append({
                    "name": collection.name,
                    "total_points": collection_details.points_count,
                    "indexed_vectors": collection_details.indexed_vectors_count if hasattr(collection_details, 'indexed_vectors_count') else "N/A",
                    "status": "ok" if collection_details.points_count > 0 else "empty",
                    "vectors": collection_details.vectors_count if hasattr(collection_details, 'vectors_count') else "N/A"
                })
        except Exception as e:
            collections_info = [{"error": str(e)}]
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "collections": collections_info,
            "connection": "active"
        }
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "message": "Database validation failed"
        }


#  Run app with Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)