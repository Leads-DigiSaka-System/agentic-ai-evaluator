from qdrant_client import QdrantClient
from src.utils.config import QDRANT_LOCAL_URI,QDRANT_COLECTION_DEMO


client = QdrantClient(url=QDRANT_LOCAL_URI)
DEMO_COLLECTION = QDRANT_COLECTION_DEMO

collection = client

