from typing import List, Any, Optional
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from qdrant_client import QdrantClient
from qdrant_client.http import models
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
        except Exception as e:
            # Handle connection errors (SSL, timeout, etc.) gracefully
            # Don't fail on startup - validation will happen on first use
            error_msg = str(e)
            if "SSL" in error_msg or "wrong version" in error_msg.lower():
                self.logger.warning(
                    f"SSL/Connection error during collection validation for '{self.collection_name}': {error_msg}. "
                    f"This might be due to HTTP/HTTPS mismatch. Validation will be retried on first use."
                )
            else:
                self.logger.warning(
                    f"Connection error during collection validation for '{self.collection_name}': {error_msg}. "
                    f"Validation will be retried on first use."
                )
            # Don't raise - allow app to start, validation will happen on first query
    
    # ✅ ONLY NEW LINE - ADD THIS DECORATOR
    @observe_operation(name="dense_vector_retrieval", capture_input=True, capture_output=True)
    def _get_relevant_documents(self, query: str, user_id: Optional[str] = None) -> List[Document]:
        """
        Retrieve documents using dense vector search with optional user_id filtering.
        
        Args:
            query: Search query string
            user_id: Optional user ID for data isolation - filters at database level for security
            
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
                "collection": self.collection_name,
                "user_id_filtered": user_id is not None
            })
            
            # ORIGINAL CODE: Encode query to vector
            query_vector = self.dense_encoder.encode([query])[0]
            
            # ✅ NEW: Log vector details
            update_trace_with_metrics({
                "vector_dimension": len(query_vector)
            })
            
            # ✅ SECURITY FIX: Build Qdrant filter at database level for user_id isolation
            # This ensures data security and better performance
            query_filter = None
            if user_id:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=user_id)
                        )
                    ]
                )
                self.logger.debug(f"Applying user_id filter at database level: {user_id}")
            
            # ✅ Search with database-level filtering for security and performance
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=(self.vector_name, query_vector),
                query_filter=query_filter,  # ✅ Filter at DB level - secure and efficient
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
    
    async def _aget_relevant_documents(self, query: str, user_id: Optional[str] = None) -> List[Document]:
        """
        Async version of _get_relevant_documents.
        
        Runs the synchronous method in a thread pool executor to avoid blocking
        the event loop during Qdrant operations and encoding.
        
        Args:
            query: Search query string
            user_id: Optional user ID for data isolation - filters at database level
            
        Returns:
            List of Document objects with metadata and scores
        """
        import asyncio
        loop = asyncio.get_event_loop()
        # Run blocking operations (encoding + Qdrant search) in thread pool
        return await loop.run_in_executor(None, self._get_relevant_documents, query, user_id)
    
    def __repr__(self) -> str:
        return (f"QdrantDenseRetriever(collection='{self.collection_name}', "
                f"vector='{self.vector_name}', limit={self.search_limit})")