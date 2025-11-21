import os
from dotenv import load_dotenv

load_dotenv()

# File Upload Settings
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg'}
ALLOWED_MIME_TYPES = ['application/pdf', 'image/png', 'image/jpeg']

# Search Settings
DEFAULT_SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "5"))
MAX_SEARCH_TOP_K = int(os.getenv("MAX_SEARCH_TOP_K", "100"))

DENSE_WEIGHT_DEFAULT = float(os.getenv("DENSE_WEIGHT", "0.7"))
SPARSE_WEIGHT_DEFAULT = float(os.getenv("SPARSE_WEIGHT", "0.3"))

# Search Quality Thresholds
MIN_SEARCH_SCORE_THRESHOLD = float(os.getenv("MIN_SEARCH_SCORE_THRESHOLD", "0.75"))  # Minimum similarity score (0.0-1.0), production-ready = 0.75

# Retry & Timeout
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "2"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "1800"))

# Quality Thresholds
ANALYSIS_CONFIDENCE_GOOD = float(os.getenv("CONFIDENCE_GOOD", "0.7"))
ANALYSIS_CONFIDENCE_ACCEPTABLE = float(os.getenv("CONFIDENCE_ACCEPTABLE", "0.4"))
GRAPH_CONFIDENCE_GOOD = float(os.getenv("GRAPH_CONFIDENCE_GOOD", "0.7"))

# CORS
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",")]

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# ============================================================================
# Cache & Storage Constants
# ============================================================================
CACHE_EXPIRY_HOURS = 24
CACHE_EXPIRY_SECONDS = CACHE_EXPIRY_HOURS * 3600

# ============================================================================
# Analysis & Processing Constants
# ============================================================================
SUMMARY_PREVIEW_LENGTH = 200
EXECUTIVE_SUMMARY_MAX_LENGTH = 500
MAX_ERROR_LIST_SIZE = 10
MIN_SUMMARY_LENGTH = 10
MAX_CONTENT_LENGTH = 4000  # For truncation

# ============================================================================
# Redis & Background Job Constants
# ============================================================================
REDIS_TRACKING_TTL_SECONDS = 3600  # 1 hour
REDIS_PROGRESS_TTL_SECONDS = 3600  # 1 hour
ARQ_JOB_TIMEOUT_SECONDS = 600  # 10 minutes
ARQ_MAX_JOBS = 10
ARQ_KEEP_RESULT_SECONDS = 86400  # 24 hours
ARQ_MAX_RETRIES = int(os.getenv("ARQ_MAX_RETRIES", "3"))  # Max retry attempts for failed jobs
ARQ_RETRY_DELAY = float(os.getenv("ARQ_RETRY_DELAY", "5.0"))  # Delay between retries in seconds
ARQ_JOB_PRIORITY_HIGH = 1
ARQ_JOB_PRIORITY_NORMAL = 5
ARQ_JOB_PRIORITY_LOW = 10

# ============================================================================
# Workflow Constants
# ============================================================================
MAX_EVALUATION_ATTEMPTS = 2
MIN_CONFIDENCE_FOR_RETRY = 0.3
SOURCE_LIMITATION_CONFIDENCE_THRESHOLD = 0.5

# ============================================================================
# File Processing Constants
# ============================================================================
TEMP_FILE_SUFFIX_PDF = ".pdf"
TEMP_FILE_SUFFIX_IMAGE = ".png"
SUPPORTED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg']