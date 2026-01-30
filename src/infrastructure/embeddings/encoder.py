from src.infrastructure.embeddings.model_loader import load_embedding_model
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
from functools import lru_cache
from typing import List

class DenseEncoder:
    """
    Dense encoder with query embedding caching for improved performance.
    
    Caches frequently used query embeddings to avoid redundant computation.
    """
    def __init__(self, cache_size: int = 1000):
        """
        Initialize dense encoder with optional caching.
        
        Args:
            cache_size: Maximum number of query embeddings to cache (default: 1000)
        """
        self.model = load_embedding_model()
        self._cache_size = cache_size
        # Create LRU cache for individual text embeddings
        self._encode_single_cached = lru_cache(maxsize=cache_size)(self._encode_single_uncached)
    
    def _encode_single_uncached(self, text: str) -> List[float]:
        """Internal method to encode a single text (uncached)."""
        return self.model.embed_documents([text])[0]
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of texts to dense vectors with caching.
        
        Individual texts are cached to improve performance for repeated queries.
        For single queries, cache is used directly. For batch queries, 
        we use the model's batch encoding which is more efficient.
        
        Args:
            texts: List of text strings to encode
            
        Returns:
            List of embedding vectors (each is a list of floats)
        """
        if not texts:
            return []
        
        # For single text, use cache (most common case for search queries)
        if len(texts) == 1:
            return [self._encode_single_cached(texts[0])]
        
        # For multiple texts, use batch encoding (more efficient than individual cache lookups)
        # The cache will still work for individual queries made separately
        return self.model.embed_documents(texts)
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._encode_single_cached.cache_clear()
    
    def get_cache_info(self):
        """Get cache statistics."""
        return self._encode_single_cached.cache_info()

class TfidfEncoder:
    def __init__(self, vectorizer_path=None, max_features=50000):
        if vectorizer_path:
            self.vectorizer = joblib.load(vectorizer_path)
        else:
            self.vectorizer = TfidfVectorizer(max_features=max_features)

    def fit(self, corpus: list[str], save_path=None):
        """Fit TF-IDF on corpus (all docs)"""
        self.vectorizer.fit(corpus)
        if save_path:
            joblib.dump(self.vectorizer, save_path)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Transform texts into fixed-length vectors"""
        arr = self.vectorizer.transform(texts).toarray()
        return arr.tolist()
