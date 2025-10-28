from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.router.upload import router as upload_router 
from src.router.search import router as search_router
from src.router.delete_extract import router as delete_router
from src.router.agent import router as agent_router
import os
from dotenv import load_dotenv
from datetime import datetime
from src.utils.config import CONNECTION_WEB
from slowapi.errors import RateLimitExceeded              # ← Keep this
from slowapi import _rate_limit_exceeded_handler          # ← Keep this
from src.utils.safe_logger import SafeLogger
from slowapi.middleware import SlowAPIMiddleware
from src.utils.limiter_config import limiter    
# Load .env
load_dotenv()

logger = SafeLogger(__name__)  # Use SafeLogger

app = FastAPI()


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
app.include_router(upload_router, prefix="/api", tags=["Upload"])
app.include_router(agent_router, prefix="/api", tags=["agent"])
app.include_router(search_router, prefix="/api", tags=["search"])
app.include_router(delete_router, prefix="/api", tags=["delete"])

# Health check endpoint
@app.get("/")
def root():
    return {"message": "Agentic AI Evaluation API is running 🚀"}

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

# REMOVE LINE 87 (the duplicate logger line)

#  Run app with Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)