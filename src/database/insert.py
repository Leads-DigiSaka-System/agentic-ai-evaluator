from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any
import uuid
import logging
import os
import numpy as np
import threading
from src.utils.config import QDRANT_LOCAL_URI, QDRANT_COLECTION_DEMO

# Encoders
from src.generator.encoder import (
    DenseEncoder,
    TfidfEncoder
)

logger = logging.getLogger(__name__)

class QdrantOperations:
    def __init__(self, dense_encoder=None, sparse_encoder=None):
        self.client = QdrantClient(url=QDRANT_LOCAL_URI)
        self.collection_name = QDRANT_COLECTION_DEMO
        self.dense_vector_name = "dense"
        self.sparse_vector_name = "sparse"
        self.dense_encoder = dense_encoder or DenseEncoder()
        
        # Thread lock for TF-IDF training
        self.tfidf_lock = threading.Lock()

        # ✅ Auto-train handling for sparse encoder
        if os.path.exists("tfidf_vectorizer.pkl"):
            print("📂 Loading existing tfidf_vectorizer.pkl (insert.py)")
            self.sparse_encoder = sparse_encoder or TfidfEncoder(vectorizer_path="tfidf_vectorizer.pkl")
        else:
            print("⚠️ tfidf_vectorizer.pkl not found (insert.py). Will start with empty TF-IDF encoder.")
            self.sparse_encoder = sparse_encoder or TfidfEncoder()

        self.default_dense_size = 768   # MiniLM default dim
        self.default_sparse_size = 50000  # TF-IDF vocab size

    def ensure_collection_exists(self, dense_size: int = 768, sparse_size: int = 50000):
        """Create collection with dense + sparse vectors"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                logger.info(f"📦 Creating collection: {self.collection_name} "
                            f"with dense={dense_size}, sparse={sparse_size}")
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
                logger.info(f"✅ Collection '{self.collection_name}' created successfully")
            else:
                logger.info(f"📦 Collection '{self.collection_name}' already exists")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to ensure collection exists: {str(e)}")
            return False

    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Insert chunks with both dense + sparse vectors
        """
        try:
            if not chunks:
                logger.warning("⚠️ No chunks to insert")
                return False

            # Prepare text contents
            texts = [chunk["content"] for chunk in chunks]

            # Compute vectors
            dense_vectors = self.dense_encoder.encode(texts)

            # ⚡ If TF-IDF not yet trained, fit on current batch with thread safety
            if not hasattr(self.sparse_encoder.vectorizer, "vocabulary_"):
                with self.tfidf_lock:  # Thread-safe training
                    # Check again inside the lock to avoid race condition
                    if not hasattr(self.sparse_encoder.vectorizer, "vocabulary_"):
                        print("⚡ Training TF-IDF (insert.py auto-train) on current chunks...")
                        self.sparse_encoder.fit(texts, save_path="tfidf_vectorizer.pkl")

            sparse_vectors = self.sparse_encoder.encode(texts)

            # Ensure collection exists
            if not self.ensure_collection_exists(
                dense_size=len(dense_vectors[0]),
                sparse_size=len(sparse_vectors[0])
            ):
                return False

            # Prepare points with metadata
            points = []
            for chunk, dv, sv in zip(chunks, dense_vectors, sparse_vectors):
                point_id = str(uuid.uuid4())

                # ✅ Convert sparse vector to Qdrant format
                sv_array = np.array(sv)
                indices = np.nonzero(sv_array)[0].tolist()
                values = sv_array[indices].tolist()
                sparse_payload = {"indices": indices, "values": values}

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
                        "char_count": chunk.get("char_count", 0)
                    }
                )

                points.append(point)

            if not points:
                logger.warning("⚠️ No valid points to insert")
                return False

            # Insert points
            logger.info(f"🚀 Inserting {len(points)} points into Qdrant...")
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True
            )

            logger.info(f"✅ Successfully inserted {len(points)} chunks into Qdrant")
            logger.info(f"📊 Operation status: {operation_info.status}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to insert chunks into Qdrant: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


# Global instance
qdrant_client = QdrantOperations()