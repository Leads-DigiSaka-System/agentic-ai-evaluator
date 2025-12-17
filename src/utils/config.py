import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GOOGLE_API_KEY = os.getenv("GEMINI_APIKEY")
GEMINI_LARGE = os.getenv("GEMINI_LARGE")

# Groq Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Default model based on Groq official docs: https://console.groq.com/docs/models
# llama-3.1-8b-instant: 131K context, $0.05/$0.08 per 1M tokens (cheapest, fast)
# llama-3.3-70b-versatile: 131K context, $0.59/$0.79 per 1M tokens (better quality)
# openai/gpt-oss-20b: 131K context, $0.075/$0.30 per 1M tokens (good balance)
# Note: mixtral-8x7b-32768 is NOT in official docs (may be deprecated)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")  # Default: 131K context, cheapest

QDRANT_LOCAL_URI_RAW = os.getenv("Qdrant_Localhost")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # Optional: For Qdrant Cloud authentication
QDRANT_COLECTION_DEMO = os.getenv("Qdrant_Form")
QDRANT_COLLECTION_ANALYSIS= os.getenv("Qdrant_Analysis_Report")

# Auto-fix common URL issues
def _normalize_qdrant_url(url: str) -> str:
    """
    Normalize Qdrant URL - handle common configuration issues
    - Remove trailing slashes
    - Auto-detect HTTP vs HTTPS (default to HTTP for local/self-hosted)
    """
    if not url:
        return url
    
    url = url.strip().rstrip('/')
    
    # If URL starts with https:// but is localhost or IP, suggest http://
    # This helps with common SSL certificate issues
    if url.startswith('https://'):
        # Check if it's a local/self-hosted instance (common SSL issues)
        if 'localhost' in url or '127.0.0.1' in url or url.count('.') <= 1:
            # Keep https:// for now, but log a warning
            pass
    
    return url

# Normalize the Qdrant URL
QDRANT_LOCAL_URI = _normalize_qdrant_url(QDRANT_LOCAL_URI_RAW) if QDRANT_LOCAL_URI_RAW else None

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

CONNECTION_WEB = os.getenv("CONNECTION_WEB","http://localhost:8501").split(",")
CONNECTION_MOBILE = os.getenv("CONNECTION_MOBILE")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Auto-detect if Langfuse is configured (all required keys present)
LANGFUSE_CONFIGURED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

#REdis
# Redis Configuration for ARQ
# Support both full REDIS_URL or individual components
REDIS_URL_ENV = os.getenv("REDIS_URL", None)  # Full Redis URL (for Railway, etc.)

if REDIS_URL_ENV:
    # Use full URL if provided (Railway, Redis Cloud connection string, etc.)
    REDIS_URL = REDIS_URL_ENV
    # Extract components for backward compatibility
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
else:
    # Build URL from individual components
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    REDIS_USERNAME = os.getenv("REDIS_USERNAME", None)  # For Railway (usually "default")
    
    # Build Redis URL with optional username and password
    if REDIS_USERNAME and REDIS_PASSWORD:
        REDIS_URL = f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    elif REDIS_PASSWORD:
        REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    else:
        REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"