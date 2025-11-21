from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any
import uuid
from src.utils.clean_logger import get_clean_logger
import os
import numpy as np
import threading
from src.utils.config import QDRANT_LOCAL_URI, QDRANT_COLECTION_DEMO, QDRANT_API_KEY

# Encoders
from src.generator.encoder import (
    DenseEncoder,
    TfidfEncoder
)

logger = get_clean_logger(__name__)

class QdrantOperations:
    def __init__(self, dense_encoder=None, sparse_encoder=None):
        # Initialize QdrantClient with optional API key for Qdrant Cloud
        if QDRANT_API_KEY:
            self.client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY)
            logger.info("QdrantOperations: Initialized with API key (Qdrant Cloud)")
        else:
            self.client = QdrantClient(url=QDRANT_LOCAL_URI)
            logger.info("QdrantOperations: Initialized without API key (local Qdrant)")
        self.collection_name = QDRANT_COLECTION_DEMO
        self.dense_vector_name = "dense"
        self.sparse_vector_name = "sparse"
        self.dense_encoder = dense_encoder or DenseEncoder()
        
        # Thread lock for TF-IDF training
        self.tfidf_lock = threading.Lock()

        # ✅ Auto-train handling for sparse encoder
        if os.path.exists("tfidf_vectorizer.pkl"):
            logger.info("Loading existing tfidf_vectorizer.pkl (insert.py)")
            self.sparse_encoder = sparse_encoder or TfidfEncoder(vectorizer_path="tfidf_vectorizer.pkl")
        else:
            logger.warning("tfidf_vectorizer.pkl not found (insert.py). Will start with empty TF-IDF encoder.")
            self.sparse_encoder = sparse_encoder or TfidfEncoder()

        self.default_dense_size = 768   # MiniLM default dim
        self.default_sparse_size = 50000  # TF-IDF vocab size

    def ensure_collection_exists(self, dense_size: int = 768, sparse_size: int = 50000):
        """Create collection with dense + sparse vectors"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                logger.storage_start("collection creation", f"name: {self.collection_name}, dense={dense_size}, sparse={sparse_size}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        self.dense_vector_name: models.VectorParams(
                            size=dense_size,
                            distance=models.Distance.COSINE
                        ),
                        self.sparse_vector_name: models.VectorParams(
                            size=sparse_size,
                            distance=models.Distance.COSINE
                        )
                    }
                )
                logger.storage_success("collection creation", 1, f"name: {self.collection_name}")
            else:
                logger.info(f"Collection '{self.collection_name}' already exists")

            return True

        except Exception as e:
            logger.storage_error("collection creation", str(e))
            return False

    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Insert chunks with both dense + sparse vectors
        """
        try:
            if not chunks:
                logger.warning("No chunks to insert")
                return False

            # Prepare text contents
            texts = [chunk["content"] for chunk in chunks]

            # Compute vectors
            dense_vectors = self.dense_encoder.encode(texts)
            
            # Validate dense vectors
            if not dense_vectors or len(dense_vectors) == 0:
                logger.error("No dense vectors generated")
                return False
            
            dense_size = len(dense_vectors[0])
            logger.debug(f"Generated {len(dense_vectors)} dense vectors of size {dense_size}")

            # ⚡ If TF-IDF not yet trained, fit on current batch with thread safety
            if not hasattr(self.sparse_encoder.vectorizer, "vocabulary_"):
                with self.tfidf_lock:  # Thread-safe training
                    # Check again inside the lock to avoid race condition
                    if not hasattr(self.sparse_encoder.vectorizer, "vocabulary_"):
                        logger.info("Training TF-IDF (insert.py auto-train) on current chunks...")
                        self.sparse_encoder.fit(texts, save_path="tfidf_vectorizer.pkl")

            sparse_vectors = self.sparse_encoder.encode(texts)
            
            # Validate sparse vectors
            if not sparse_vectors or len(sparse_vectors) == 0:
                logger.error("No sparse vectors generated")
                return False
            
            sparse_size = len(sparse_vectors[0])
            logger.debug(f"Generated {len(sparse_vectors)} sparse vectors of size {sparse_size}")
            
            # Validate vector dimensions match
            if len(dense_vectors) != len(sparse_vectors):
                logger.error(f"Vector count mismatch: {len(dense_vectors)} dense vs {len(sparse_vectors)} sparse")
                return False

            # Get actual vector sizes
            dense_size = len(dense_vectors[0])
            sparse_size = len(sparse_vectors[0])
            
            # Validate vector sizes
            if dense_size <= 0 or sparse_size <= 0:
                logger.error(f"Invalid vector sizes: dense={dense_size}, sparse={sparse_size}")
                return False
            
            # Ensure collection exists with correct dimensions
            if not self.ensure_collection_exists(
                dense_size=dense_size,
                sparse_size=sparse_size
            ):
                logger.error("Failed to ensure collection exists with correct dimensions")
                return False
            
            # Verify collection configuration matches
            try:
                collection_info = self.client.get_collection(self.collection_name)
                # Check if collection has the right vector configuration
                if hasattr(collection_info.config, 'params') and hasattr(collection_info.config.params, 'vectors'):
                    vectors_config = collection_info.config.params.vectors
                    if isinstance(vectors_config, dict):
                        if self.sparse_vector_name in vectors_config:
                            expected_sparse_size = vectors_config[self.sparse_vector_name].size
                            if expected_sparse_size != sparse_size:
                                logger.warning(
                                    f"Sparse vector size mismatch: collection expects {expected_sparse_size}, "
                                    f"but got {sparse_size}. This may cause errors."
                                )
            except Exception as e:
                logger.warning(f"Could not verify collection configuration: {e}")

            # Prepare points with metadata
            points = []
            for chunk, dv, sv in zip(chunks, dense_vectors, sparse_vectors):
                point_id = str(uuid.uuid4())

                # ✅ Convert sparse vector to Qdrant format
                # Ensure proper format: indices as integers, values as floats
                sv_array = np.array(sv, dtype=np.float32)
                
                # Find non-zero elements (with small threshold to avoid floating point issues)
                threshold = 1e-8
                nonzero_mask = np.abs(sv_array) > threshold
                indices = np.where(nonzero_mask)[0].astype(int).tolist()
                values = sv_array[nonzero_mask].astype(float).tolist()
                
                # Validate sparse vector format
                if len(indices) == 0:
                    logger.warning(f"Empty sparse vector for chunk {chunk.get('chunk_id', 'unknown')}, using empty sparse vector")
                    indices = []
                    values = []
                else:
                    # Ensure indices are within bounds (must be < sparse_size)
                    max_index = max(indices) if indices else 0
                    if max_index >= sparse_size:
                        logger.warning(
                            f"Sparse vector index {max_index} exceeds collection size {sparse_size}. "
                            f"Truncating to valid range."
                        )
                        valid_mask = [idx < sparse_size for idx in indices]
                        indices = [idx for idx, valid in zip(indices, valid_mask) if valid]
                        values = [val for val, valid in zip(values, valid_mask) if valid]
                    
                    # Ensure indices are sorted (Qdrant requirement)
                    if indices != sorted(indices):
                        sorted_pairs = sorted(zip(indices, values))
                        indices = [idx for idx, _ in sorted_pairs]
                        values = [val for _, val in sorted_pairs]
                    
                    # Validate: indices must be non-negative integers, values must be finite floats
                    indices = [int(idx) for idx in indices if idx >= 0]
                    values = [float(val) for val in values]
                    
                    # Filter out any invalid values (NaN, Inf)
                    valid_mask = [np.isfinite(v) for v in values]
                    indices = [idx for idx, valid in zip(indices, valid_mask) if valid]
                    values = [val for val, valid in zip(values, valid_mask) if valid]
                    
                    # Remove duplicates (keep last value if duplicate indices)
                    if len(indices) != len(set(indices)):
                        seen = {}
                        for idx, val in zip(indices, values):
                            seen[idx] = val
                        indices = sorted(seen.keys())
                        values = [seen[idx] for idx in indices]

                point = models.PointStruct(
                    id=point_id,
                    vector={
                        self.dense_vector_name: dv,
                        self.sparse_vector_name: models.SparseVector(
                            indices=indices,
                            values=values
                        )
                    },
                    payload={
                        "content": chunk["content"],
                        "chunk_id": chunk.get("chunk_id", ""),
                        "form_id": chunk.get("metadata", {}).get("form_id", "unknown_id"),
                        "form_title": chunk.get("metadata", {}).get("form_title", "Unknown Title"),
                        "form_type": chunk.get("metadata", {}).get("form_type", "Unknown Type"),
                        "date_of_insertion": chunk.get("metadata", {}).get("date_of_insertion", "unknown_date"),
                        "token_count": chunk.get("token_count", 0),
                        "char_count": chunk.get("char_count", 0),
                        # ✅ Add user_id from metadata for multi-user isolation
                        "user_id": chunk.get("metadata", {}).get("user_id")
                    }
                )

                points.append(point)

            if not points:
                logger.warning("No valid points to insert")
                return False

            # Insert points
            # ✅ Log user_id if present for verification
            user_ids_in_batch = [p.payload.get("user_id") for p in points if p.payload.get("user_id")]
            user_id_info = f" (user_id: {user_ids_in_batch[0]})" if user_ids_in_batch else ""
            logger.storage_start("chunk insertion", f"count: {len(points)}{user_id_info}")
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True
            )

            logger.storage_success("chunk insertion", len(points))
            logger.info(f"Operation status: {operation_info.status}")
            return True

        except Exception as e:
            logger.storage_error("chunk insertion", str(e))
            import traceback
            traceback.print_exc()
            return False


# Global instance
qdrant_client = QdrantOperations()