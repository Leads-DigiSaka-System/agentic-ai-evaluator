import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GOOGLE_API_KEY = os.getenv("GEMINI_APIKEY")
GEMINI_LARGE = os.getenv("GEMINI_LARGE")

# Groq Configuration (Legacy - can be replaced with OpenRouter)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Default to free tier model (llama-3.1-8b-instant is typically free)
# For reasoning: use "deepseek-r1-distill-llama-70b" (paid, ~$0.75-0.99/M tokens)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")  # Default to free tier model

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Default to free Llama 3.3 70B Instruct model
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")


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

# Only use API key when URL is HTTPS (avoids "Api key is used with an insecure connection" warning)
QDRANT_USE_API_KEY = bool(
    QDRANT_API_KEY
    and QDRANT_LOCAL_URI
    and str(QDRANT_LOCAL_URI).strip().lower().startswith("https://")
)

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

# PostgreSQL Configuration (for LangChain checkpointer)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "agentic_ai_evaluator")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Build PostgreSQL URL
def get_postgres_url() -> str:
    """Get PostgreSQL connection URL"""
    postgres_url = os.getenv("POSTGRES_URL")
    if postgres_url:
        return postgres_url
    
    if POSTGRES_PASSWORD:
        return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    else:
        return f"postgresql://{POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

POSTGRES_URL = get_postgres_url()

# Chat Agent Configuration
# Maximum number of messages to use for conversation context
# Lower = less token usage, less context. Higher = more context, more tokens
MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "10"))

# Maximum number of messages to load from PostgreSQL memory
# This prevents loading too many messages and hitting token limits
MAX_MESSAGES_TO_LOAD = int(os.getenv("MAX_MESSAGES_TO_LOAD", "10"))

# Agent Cache Configuration
# Maximum number of cached agents (LRU cache)
MAX_CACHE_SIZE = int(os.getenv("MAX_CACHE_SIZE", "50"))

# Cache TTL in hours - how long to keep agents in cache
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

# LLM Retry Configuration
# Maximum number of retry attempts for LLM API calls
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))

# LLM timeout in seconds for each API call
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

# Session timeout configuration
# Session expires after this many minutes of inactivity (default: 30 minutes)
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
# Auto-cleanup expired sessions older than this many days (default: 7 days)
SESSION_CLEANUP_DAYS = int(os.getenv("SESSION_CLEANUP_DAYS", "7"))

# Retry delay configuration (exponential backoff)
# Base delay in seconds (will be multiplied by 2^attempt)
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "1.0"))

# Maximum delay in seconds (caps exponential backoff)
LLM_RETRY_MAX_DELAY = float(os.getenv("LLM_RETRY_MAX_DELAY", "10.0"))

# PostgreSQL Connection Pool Configuration
# Minimum number of connections to keep in pool
POSTGRES_POOL_MIN = int(os.getenv("POSTGRES_POOL_MIN", "2"))
# Maximum number of connections in pool
POSTGRES_POOL_MAX = int(os.getenv("POSTGRES_POOL_MAX", "10"))


def validate_config():
    """
    Validate configuration on startup.
    
    Checks for required environment variables and validates their format.
    Fails fast if critical configs are missing.
    
    Returns:
        tuple: (critical_errors, warnings)
        - critical_errors: List of missing critical configs (will prevent startup)
        - warnings: List of optional but recommended configs that are missing
    
    Raises:
        ValueError: If critical configuration is missing
    """
    critical_errors = []
    warnings = []
    
    # ============================================================================
    # CRITICAL CONFIGURATION (Required for app to function)
    # ============================================================================
    
    # API Security
    if not os.getenv("API_KEY"):
        critical_errors.append("API_KEY is required for API security")
    
    # Vector Database (Qdrant) - Required for search functionality
    if not QDRANT_LOCAL_URI_RAW:
        critical_errors.append("Qdrant_Localhost is required (vector database URL)")
    elif not QDRANT_LOCAL_URI_RAW.startswith(("http://", "https://")):
        critical_errors.append(f"Qdrant_Localhost must be a valid URL (http:// or https://), got: {QDRANT_LOCAL_URI_RAW}")
    
    if not QDRANT_COLECTION_DEMO:
        critical_errors.append("Qdrant_Form is required (form collection name)")
    
    if not QDRANT_COLLECTION_ANALYSIS:
        critical_errors.append("Qdrant_Analysis_Report is required (analysis collection name)")
    
    # Embedding Model - Required for vector search
    if not EMBEDDING_MODEL:
        critical_errors.append("EMBEDDING_MODEL is required (e.g., BAAI/bge-small-en-v1.5)")
    
    # Redis - Required for ARQ worker (background jobs)
    if not REDIS_URL_ENV and not os.getenv("REDIS_HOST"):
        critical_errors.append("REDIS_URL or REDIS_HOST is required (for ARQ worker)")
    
    # LLM Provider - At least one must be configured
    if not GOOGLE_API_KEY and not OPENROUTER_API_KEY:
        critical_errors.append("At least one LLM provider is required: GEMINI_APIKEY or OPENROUTER_API_KEY")
    
    # ============================================================================
    # WARNINGS (Optional but recommended)
    # ============================================================================
    
    # Chat Agent - Recommended for chat functionality
    if not OPENROUTER_API_KEY:
        warnings.append("OPENROUTER_API_KEY is not set - Chat Agent will not work (use GEMINI_APIKEY for other features)")
    
    # PostgreSQL - Recommended for persistent chat memory
    if not os.getenv("POSTGRES_URL") and POSTGRES_HOST == "localhost" and POSTGRES_PASSWORD == "":
        warnings.append("POSTGRES_URL not configured - Chat Agent will use in-memory memory (not persistent)")
    
    # Langfuse - Optional but recommended for observability
    if not LANGFUSE_CONFIGURED:
        warnings.append("Langfuse not configured - Observability disabled (set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)")
    
    return critical_errors, warnings


def validate_and_log_config():
    """
    Validate configuration and log results.
    Raises ValueError if critical configs are missing.
    """
    from src.shared.logging.clean_logger import get_clean_logger
    logger = get_clean_logger(__name__)
    
    logger.info("🔍 Validating configuration...")
    
    critical_errors, warnings = validate_config()
    
    # Log warnings (non-critical)
    if warnings:
        logger.warning("⚠️ Configuration warnings (non-critical):")
        for warning in warnings:
            logger.warning(f"   - {warning}")
    
    # Log and raise for critical errors
    if critical_errors:
        logger.error("❌ Critical configuration errors found:")
        for error in critical_errors:
            logger.error(f"   - {error}")
        logger.error("")
        logger.error("💡 Please check your .env file and ensure all required variables are set.")
        logger.error("   See env.example for a template of required configuration.")
        raise ValueError(
            f"Critical configuration missing: {len(critical_errors)} error(s). "
            "Check logs above for details."
        )
    
    # Success
    logger.info("✅ Configuration validation passed")
    
    # Log key configuration status
    logger.info("📋 Configuration summary:")
    logger.info(f"   - API Key: {'✅ Set' if os.getenv('API_KEY') else '❌ Missing'}")
    logger.info(f"   - Qdrant: {'✅ Configured' if QDRANT_LOCAL_URI else '❌ Missing'}")
    logger.info(f"   - Embedding Model: {'✅ ' + EMBEDDING_MODEL if EMBEDDING_MODEL else '❌ Missing'}")
    logger.info(f"   - Redis: {'✅ Configured' if REDIS_URL else '❌ Missing'}")
    logger.info(f"   - Gemini API: {'✅ Configured' if GOOGLE_API_KEY else '❌ Not set'}")
    logger.info(f"   - OpenRouter API: {'✅ Configured' if OPENROUTER_API_KEY else '❌ Not set'}")
    logger.info(f"   - PostgreSQL: {'✅ Configured' if os.getenv('POSTGRES_URL') or POSTGRES_PASSWORD else '⚠️ Using defaults'}")
    logger.info(f"   - Langfuse: {'✅ Configured' if LANGFUSE_CONFIGURED else '⚠️ Not configured'}")