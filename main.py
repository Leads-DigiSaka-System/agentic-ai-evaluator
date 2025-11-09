from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from src.router.upload import router as upload_router 
from src.router.search import router as search_router
#from src.router.delete_extract import router as delete_router
from src.router.agent import router as agent_router
from src.router.storage import router as storage_router
from src.deps.security import require_api_key
import os
import signal
import atexit
from dotenv import load_dotenv
from datetime import datetime
from src.utils.config import CONNECTION_WEB
from slowapi.errors import RateLimitExceeded              
from slowapi import _rate_limit_exceeded_handler          
from src.utils.safe_logger import SafeLogger
from src.utils.simple_clean_logging import setup_clean_logging, get_clean_logger
from slowapi.middleware import SlowAPIMiddleware
from src.utils.limiter_config import limiter    

# Load .env
load_dotenv()

# Setup clean logging with colors
setup_clean_logging("INFO")
logger = get_clean_logger(__name__)

# ⚠️ CRITICAL: Initialize Langfuse v3 BEFORE importing routes
# This ensures Langfuse is ready when nodes are imported
try:
    from src.monitoring.trace.langfuse_helper import initialize_langfuse
    if initialize_langfuse():
        logger.info("✅ Langfuse v3 initialized successfully")
    else:
        logger.info("ℹ️ Langfuse not configured or initialization skipped")
except Exception as e:
    logger.warning(f"⚠️ Langfuse initialization failed: {e}")
    logger.info("ℹ️ Continuing without Langfuse observability")

# Graceful shutdown handler
def shutdown_handler():
    """Handle graceful shutdown"""
    logger.info("Shutting down gracefully...")
    logger.info("Closing database connections...")
    
    # Flush and shutdown Langfuse
    try:
        from src.monitoring.trace.langfuse_helper import flush_langfuse, shutdown_langfuse
        flush_langfuse()
        shutdown_langfuse()
        logger.info("✅ Langfuse flushed and shutdown")
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

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

app = FastAPI()

# Add FastAPI shutdown event for Langfuse
@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event - flush Langfuse before shutdown"""
    try:
        from src.monitoring.trace.langfuse_helper import flush_langfuse, shutdown_langfuse
        flush_langfuse()
        shutdown_langfuse()
        logger.info("✅ Langfuse flushed on FastAPI shutdown")
    except Exception as e:
        logger.debug(f"Langfuse shutdown error (non-critical): {e}")


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
# Initialize FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CONNECTION_WEB], # ← Fixed: Use list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Secure all API routes with API key. Health and admin validate can remain open if desired.
app.include_router(upload_router, prefix="/api", tags=["Upload"], dependencies=[Depends(require_api_key)])
app.include_router(agent_router, prefix="/api", tags=["agent"], dependencies=[Depends(require_api_key)])  # Re-enabled with debug
app.include_router(search_router, prefix="/api", tags=["search"], dependencies=[Depends(require_api_key)])
#app.include_router(delete_router, prefix="/api", tags=["delete"], dependencies=[Depends(require_api_key)])
app.include_router(storage_router, prefix="/api", tags=["storage"], dependencies=[Depends(require_api_key)])  # Re-enabled with debug

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
    
    # Check Database
    try:
        from src.database.insert import qdrant_client
        collections = qdrant_client.client.get_collections()
        health_status["checks"]["database"] = {
            "status": "ok",
            "collections": len(collections.collections)
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["database"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check LLM (Gemini)
    try:
        from src.utils.llm_helper import llm
        health_status["checks"]["llm"] = {"status": "ok"}
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["llm"] = {
            "status": "error",
            "error": str(e)
        }
    
    return health_status

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
        from src.database.insert import qdrant_client
        
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