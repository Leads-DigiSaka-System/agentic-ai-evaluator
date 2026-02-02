from qdrant_client import QdrantClient
from src.core.config import QDRANT_LOCAL_URI, QDRANT_COLECTION_DEMO, QDRANT_USE_API_KEY, QDRANT_API_KEY
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)

# Initialize QdrantClient with optional API key (only when URL is HTTPS)
# If QDRANT_USE_API_KEY is True, use API key (Qdrant Cloud over HTTPS)
# Otherwise connect without API key (local Qdrant or public instance)
# Increased timeout for remote Qdrant servers (60 seconds)
if QDRANT_USE_API_KEY:
    client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=60)
    logger.info("QdrantClient initialized with API key (Qdrant Cloud)")
else:
    client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=60)
    logger.info("QdrantClient initialized without API key (local or public instance)")

DEMO_COLLECTION = QDRANT_COLECTION_DEMO
collection = client

