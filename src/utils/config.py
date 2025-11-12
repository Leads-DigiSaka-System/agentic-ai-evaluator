import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GOOGLE_API_KEY = os.getenv("GEMINI_APIKEY")
GEMINI_LARGE = os.getenv("GEMINI_LARGE")

QDRANT_LOCAL_URI = os.getenv("Qdrant_Localhost")
QDRANT_COLECTION_DEMO = os.getenv("Qdrant_Form")
QDRANT_COLLECTION_ANALYSIS= os.getenv("Qdrant_Analysis_Report")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

CONNECTION_WEB = os.getenv("CONNECTION_WEB","http://localhost:8501").split(",")
CONNECTION_MOBILE = os.getenv("CONNECTION_MOBILE")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Auto-detect if Langfuse is configured (all required keys present)
LANGFUSE_CONFIGURED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)