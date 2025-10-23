from typing import List, Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from src.generator.encoder import DenseEncoder
from pydantic import Field, PrivateAttr
import logging

logger = logging.getLogger(__name__)


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
    
    def _validate_collection(self) -> None:
        """Validate that the collection exists in Qdrant"""
        try:
            self.client.get_collection(self.collection_name)
            logger.debug(f"✅ Collection '{self.collection_name}' validated")
        except UnexpectedResponse:
            logger.error(f"❌ Collection '{self.collection_name}' does not exist")
            raise ValueError(f"Collection '{self.collection_name}' not found in Qdrant")
    
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
            logger.warning("⚠️ Empty query provided")
            return []
        
        try:
            # Encode query to vector
            query_vector = self.dense_encoder.encode([query])[0]
            
            # Perform search in Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=(self.vector_name, query_vector),
                limit=self.search_limit,
                with_payload=True
            )
            
            # Convert to LangChain Document format
            documents = []
            for result in search_results:
                doc = Document(
                    page_content=result.payload.get("summary_text", ""),
                    metadata={
                        **result.payload,
                        "score": result.score,
                        "id": result.id
                    }
                )
                documents.append(doc)
            
            logger.info(f"🔍 Found {len(documents)} documents for query: '{query[:50]}...'")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Search failed for query '{query[:50]}...': {str(e)}")
            raise
    
    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """Async version - delegates to sync method"""
        return self._get_relevant_documents(query)
    
    def __repr__(self) -> str:
        return (f"QdrantDenseRetriever(collection='{self.collection_name}', "
                f"vector='{self.vector_name}', limit={self.search_limit})")