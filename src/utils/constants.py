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

# Retry & Timeout
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "2"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "300"))

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