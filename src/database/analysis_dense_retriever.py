from typing import List, Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from src.generator.encoder import DenseEncoder
from src.utils.clean_logger import get_clean_logger
from pydantic import Field, PrivateAttr
from src.monitoring.trace.langfuse_helper import (
    observe_operation,
    update_trace_with_metrics, 
    update_trace_with_error
    )

class QdrantDenseRetriever(BaseRetriever):
    """
    Dense vector retriever for Qdrant collections.
    
    Uses dense embeddings to perform semantic similarity search
    across stored analysis documents.
    
    Args:
        client: Initialized QdrantClient instance
        collection_name: Name of the Qdrant collection
        dense_encoder: Encoder instance for generating embeddings
        vector_name: Name of the vector field in Qdrant (default: "dense")
        search_limit: Maximum number of results to return (default: 10)
    
    Example:
        >>> retriever = QdrantDenseRetriever(
        ...     client=client,
        ...     collection_name="analysis",
        ...     dense_encoder=encoder
        ... )
        >>> docs = retriever.get_relevant_documents("corn yield improvement")
    """
    
    # Use PrivateAttr for complex objects that shouldn't be serialized
    _client: QdrantClient = PrivateAttr()
    _dense_encoder: DenseEncoder = PrivateAttr()
    
    # Regular fields for simple types
    collection_name: str = Field(...)
    vector_name: str = Field(default="dense")
    search_limit: int = Field(default=10)
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        dense_encoder: DenseEncoder,
        vector_name: str = "dense",
        search_limit: int = 10
    ):
        super().__init__(
            collection_name=collection_name,
            vector_name=vector_name,
            search_limit=search_limit
        )
        # Use object.__setattr__ for private attributes
        object.__setattr__(self, '_client', client)
        object.__setattr__(self, '_dense_encoder', dense_encoder)
        object.__setattr__(self, '_logger', get_clean_logger(__name__))
        
        # Validate collection exists
        self._validate_collection()
    
    @property
    def client(self) -> QdrantClient:
        """Access the QdrantClient instance"""
        return self._client
    
    @property
    def dense_encoder(self) -> DenseEncoder:
        """Access the DenseEncoder instance"""
        return self._dense_encoder
    
    @property
    def logger(self):
        """Access the logger instance"""
        return self._logger
    
    def _validate_collection(self) -> None:
        """Validate that the collection exists in Qdrant"""
        try:
            self.client.get_collection(self.collection_name)
            self.logger.debug(f"Collection '{self.collection_name}' validated")
        except UnexpectedResponse:
            self.logger.error(f"Collection '{self.collection_name}' does not exist")
            raise ValueError(f"Collection '{self.collection_name}' not found in Qdrant")
    
    # ✅ ONLY NEW LINE - ADD THIS DECORATOR
    @observe_operation(name="dense_vector_retrieval", capture_input=True, capture_output=True)
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """
        Retrieve documents using dense vector search.
        
        Args:
            query: Search query string
            
        Returns:
            List of Document objects with metadata and scores
            
        Raises:
            ValueError: If query is empty or encoding fails
        """
        if not query or not query.strip():
            self.logger.warning("Empty query provided")
            return []
        
        try:
            # ✅ NEW: Log search parameters
            update_trace_with_metrics({
                "query_length": len(query),
                "vector_name": self.vector_name,
                "search_limit": self.search_limit,
                "collection": self.collection_name
            })
            
            # ORIGINAL CODE: Encode query to vector
            query_vector = self.dense_encoder.encode([query])[0]
            
            # ✅ NEW: Log vector details
            update_trace_with_metrics({
                "vector_dimension": len(query_vector)
            })
            
            # ORIGINAL CODE: Perform search in Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=(self.vector_name, query_vector),
                limit=self.search_limit,
                with_payload=True
            )
            
            # ✅ NEW: Log search results
            if search_results:
                scores = [result.score for result in search_results]
                update_trace_with_metrics({
                    "results_found": len(search_results),
                    "top_score": scores[0],
                    "avg_score": sum(scores) / len(scores)
                })
            
            # ORIGINAL CODE: Convert to LangChain Document format
            documents = []
            for result in search_results:
                # Extract user_id from payload for filtering
                payload = result.payload or {}
                doc = Document(
                    page_content=payload.get("summary_text", ""),
                    metadata={
                        **payload,  # Include all payload fields (including user_id if present)
                        "score": result.score,
                        "id": result.id
                    }
                )
                documents.append(doc)
            
            # ORIGINAL CODE: Log and return
            self.logger.db_query("dense search", f"query: '{query[:50]}...'", len(documents))
            return documents
            
        except Exception as e:
            # ✅ NEW: Log error to trace (1 new line added)
            update_trace_with_error(e, {"operation": "dense_retrieval", "collection": self.collection_name})
            # ORIGINAL CODE: Log error
            self.logger.db_error("dense search", str(e))
            raise
    
    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """Async version - delegates to sync method"""
        return self._get_relevant_documents(query)
    
    def __repr__(self) -> str:
        return (f"QdrantDenseRetriever(collection='{self.collection_name}', "
                f"vector='{self.vector_name}', limit={self.search_limit})")