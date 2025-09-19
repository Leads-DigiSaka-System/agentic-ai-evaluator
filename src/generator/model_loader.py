# file: src/utils/model_loader.py
from functools import lru_cache
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import SentenceTransformersTokenTextSplitter
from src.utils.config import EMBEDDING_MODEL

@lru_cache(maxsize=1)
def load_embedding_model():
    """
    Load and cache HuggingFace embedding model.
    Example EMBEDDING_MODEL values:
      - "intfloat/multilingual-e5-base"
      - "sentence-transformers/all-MiniLM-L6-v2"
    """
    print(f"⚡ Loading embedding model: {EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

@lru_cache(maxsize=1)
def load_token_splitter():
    """
    Load and cache token-based text splitter
    using the same model as the embedding model.
    """
    print(f"⚡ Loading token splitter (based on {EMBEDDING_MODEL})")
    return SentenceTransformersTokenTextSplitter(
        model_name=EMBEDDING_MODEL,
        chunk_size=400,   # safe for e5-base
        chunk_overlap=50
    )
