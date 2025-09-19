from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any
import uuid
from src.utils.config import QDRANT_LOCAL_URI, QDRANT_COLECTION_DEMO

class QdrantOperations:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_LOCAL_URI)
        self.collection_name = QDRANT_COLECTION_DEMO
        self.dense_vector_name = "dense"  # For your embeddings
        self.sparse_vector_name = "sparse"  # For future sparse vectors
    
    def ensure_collection_exists(self, dense_vector_size: int = 768, sparse_vector_size: int = 10000):
        """Create collection for hybrid search with both dense and sparse vectors"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                print(f"📦 Creating hybrid collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        self.dense_vector_name: models.VectorParams(
                            size=dense_vector_size,
                            distance=models.Distance.COSINE
                        ),
                        # Comment out sparse if you're not using it yet
                        # self.sparse_vector_name: models.VectorParams(
                        #     size=sparse_vector_size,
                        #     distance=models.Distance.DOT
                        # )
                    }
                )
                print(f"✅ Hybrid collection '{self.collection_name}' created successfully")
            else:
                print(f"📦 Collection '{self.collection_name}' already exists")
                # Check collection configuration
                collection_info = self.client.get_collection(self.collection_name)
                print(f"Collection config: {collection_info.config.params}")
                
            return True
                
        except Exception as e:
            print(f"❌ Failed to ensure collection exists: {str(e)}")
            return False
    
    def insert_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Insert embedded chunks into Qdrant with named dense vectors
        """
        try:
            if not chunks:
                print("⚠️ No chunks to insert")
                return False
            
            # Check embedding dimension
            embedding_size = len(chunks[0]['embedding']) if chunks else 384
            print(f"📏 Embedding dimension: {embedding_size}")
            
            # Ensure collection exists with correct vector size
            if not self.ensure_collection_exists(dense_vector_size=embedding_size):
                return False
            
            # Prepare points for insertion with named vectors
            points = []
            for chunk in chunks:
                if 'embedding' not in chunk:
                    print(f"⚠️ Skipping chunk {chunk.get('chunk_id', 'unknown')} - no embedding")
                    continue
                
                point_id = str(uuid.uuid4())
                
                point = models.PointStruct(
                    id=point_id,
                    vector={
                        self.dense_vector_name: chunk['embedding']  # Named dense vector
                        # Add sparse vectors here when you have them:
                        # self.sparse_vector_name: chunk.get('sparse_embedding', [])
                    },
                    payload={
                        "content": chunk['content'],
                        "chunk_id": chunk.get('chunk_id', ''),
                        "token_count": chunk.get('token_count', 0),
                        "char_count": chunk.get('char_count', 0),
                        "metadata": chunk.get('metadata', {}),
                        "type": chunk.get('metadata', {}).get('type', 'unknown'),
                        "original_document": "uploaded_pdf"
                    }
                )
                points.append(point)
            
            if not points:
                print("⚠️ No valid points to insert")
                return False
            
            # Insert points in batch
            print(f"🚀 Inserting {len(points)} points into Qdrant...")
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True
            )
            
            print(f"✅ Successfully inserted {len(points)} chunks into Qdrant")
            print(f"📊 Operation status: {operation_info.status}")
            
            # Verify insertion
            count_result = self.client.count(
                collection_name=self.collection_name,
                exact=True
            )
            print(f"📈 Total points in collection: {count_result.count}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to insert chunks into Qdrant: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

qdrant_client = QdrantOperations()