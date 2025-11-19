from typing import List, Any, Optional
import numpy as np
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from qdrant_client.http import models
from pydantic import Field
from src.utils.clean_logger import get_clean_logger

class QdrantSparseRetriever(BaseRetriever):
    """
    Custom sparse vector retriever for Qdrant that performs keyword-based search.
    
    This retriever converts text queries into sparse vectors and searches
    for documents with matching keywords/terms in the Qdrant vector database.
    
    Sparse vectors are good at finding:
    - Exact keyword matches
    - Specific terminology
    - Technical terms and proper nouns
    - Rare or unique words
    """
    
    # Define these as Pydantic fields
    client: Any = Field(description="Qdrant client instance")
    collection_name: str = Field(description="Name of the Qdrant collection")
    sparse_encoder: Any = Field(description="Encoder for creating sparse vectors")
    vector_name: str = Field(description="Name of the sparse vector field in Qdrant")
    search_limit: int = Field(default=10, description="Maximum number of results to retrieve")
    
    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True  # Allow non-Pydantic types like Qdrant client
    
    def _encode_sparse_query(self, query: str) -> dict:
        """
        Convert text query to sparse vector format required by Qdrant.
        
        Sparse vectors are stored as:
        - indices: positions of non-zero values
        - values: the actual non-zero values
        
        This is memory efficient since most values are zero.
        
        Args:
            query: Text query to encode
            
        Returns:
            Dictionary with 'indices' and 'values' lists
        """
        try:
            # Check if encoder already returns Qdrant-compatible format
            if hasattr(self.sparse_encoder, 'encode_to_qdrant_format'):
                return self.sparse_encoder.encode_to_qdrant_format(query)
            
            # Get dense TF-IDF vector (this is the issue!)
            sparse_vec = self.sparse_encoder.encode([query])[0]
            
            # ✅ IMPROVEMENT: Use proper logging instead of print statements
            logger = get_clean_logger(__name__)
            
            # Debug: Check if we got any non-zero values
            if hasattr(sparse_vec, 'nnz'):
                # It's a scipy sparse matrix
                if sparse_vec.nnz == 0:
                    logger.warning(
                        f"TF-IDF returned zero vector for query: '{query}'. "
                        "Query terms are not in the TF-IDF vocabulary (OOV - Out of Vocabulary). "
                        "Consider using query expansion or falling back to dense retriever."
                    )
                    # Return empty sparse vector
                    return {"indices": [], "values": []}
                
                # Convert scipy sparse to arrays
                sparse_vec = sparse_vec.toarray()[0] if hasattr(sparse_vec, 'toarray') else sparse_vec
            
            # Convert to numpy array for processing
            sv_array = np.array(sparse_vec)
            
            # Find non-zero positions and values
            indices = np.nonzero(sv_array)[0].tolist()
            values = sv_array[indices].tolist()
            
            # ✅ IMPROVEMENT: Proper logging with context
            if len(indices) == 0:
                logger.warning(
                    f"No non-zero values found for query: '{query}'. "
                    f"TF-IDF vector shape: {sv_array.shape}, max value: {sv_array.max()}. "
                    "This may indicate vocabulary mismatch or empty query."
                )
            else:
                logger.debug(
                    f"Query '{query}' encoded to sparse vector: {len(indices)} non-zero terms, "
                    f"max value: {max(values):.6f}"
                )
            
            return {"indices": indices, "values": values}
            
        except Exception as e:
            logger = get_clean_logger(__name__)
            logger.error(f"Error encoding sparse query '{query}': {str(e)}", exc_info=True)
            return {"indices": [], "values": []}
    
    def _get_relevant_documents(
        self, 
        query: str, 
        *, 
        run_manager: CallbackManagerForRetrieverRun,
        user_id: Optional[str] = None
    ) -> List[Document]:
        """
        Retrieve documents using sparse vector keyword search with optional user_id filtering.
        
        Process:
        1. Convert the text query into a sparse vector
        2. Search Qdrant for documents with matching keywords (with optional user_id filter)
        3. Convert results to LangChain Document format
        
        Args:
            query: The search query text
            run_manager: LangChain callback manager (for logging/tracing)
            user_id: Optional user ID for data isolation - filters at database level
            
        Returns:
            List of LangChain Document objects with content and metadata
        """
        logger = get_clean_logger(__name__)
        
        try:
            # Step 1: Encode query to sparse vector
            sparse_vector = self._encode_sparse_query(query)
            
            # ✅ IMPROVEMENT: Handle OOV (Out of Vocabulary) queries gracefully
            if len(sparse_vector["indices"]) == 0:
                logger.warning(
                    f"Empty sparse vector for query '{query}'. "
                    "This query has no matching terms in TF-IDF vocabulary. "
                    "Consider falling back to dense retriever or using query expansion."
                )
                # Return empty results - caller can fall back to dense retriever
                return []
            
            # ✅ SECURITY FIX: Build Qdrant filter at database level for user_id isolation
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
                logger.debug(f"Applying user_id filter at database level: {user_id}")
            
            # Step 2: Search Qdrant using sparse vector matching with optional filter
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=models.NamedSparseVector(
                    name=self.vector_name,
                    vector=sparse_vector
                ),
                query_filter=query_filter,  # ✅ Filter at DB level - secure and efficient
                limit=self.search_limit,
                with_payload=True  # Include document metadata
            )
            
            # Step 3: Convert to LangChain Documents
            documents = []
            for result in results:
                doc = Document(
                    page_content=result.payload.get("content", ""),
                    metadata={
                        "id": result.id,
                        "score": result.score,
                        "retriever_type": "sparse",  # Track which retriever found this
                        "form_id": result.payload.get("form_id", ""),
                        "form_title": result.payload.get("form_title", ""),
                        "form_type": result.payload.get("form_type", ""),
                        "date_of_insertion": result.payload.get("date_of_insertion", ""),
                        "matched_terms": self._extract_query_terms(query)  # For debugging
                    }
                )
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            # Log error and return empty list to prevent crashes
            if run_manager:
                run_manager.on_retriever_error(e)
            logger.error(f"Error in sparse retrieval for query '{query}': {str(e)}", exc_info=True)
            return []
    
    def _extract_query_terms(self, query: str) -> List[str]:
        """
        Extract key terms from the query for debugging purposes.
        
        Args:
            query: Original query text
            
        Returns:
            List of important terms from the query
        """
        # Simple term extraction (you might want to use more sophisticated methods)
        terms = query.lower().split()
        # Remove common stop words
        stop_words = {'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but'}
        return [term for term in terms if term not in stop_words and len(term) > 2]
    
    def update_search_limit(self, new_limit: int):
        """
        Update the maximum number of results to retrieve.
        
        Args:
            new_limit: New limit for search results
        """
        self.search_limit = new_limit
    
    def get_encoder_info(self) -> dict:
        """
        Get information about the sparse encoder being used.
        
        Returns:
            Dictionary with encoder information
        """
        return {
            "encoder_type": type(self.sparse_encoder).__name__,
            "vector_name": self.vector_name,
            "search_limit": self.search_limit
        }
    
    def test_encoding(self, query: str) -> dict:
        """
        Test the sparse encoding for a given query (useful for debugging).
        
        Args:
            query: Query to test
            
        Returns:
            Dictionary with encoding information
        """
        sparse_vector = self._encode_sparse_query(query)
        return {
            "query": query,
            "num_nonzero_terms": len(sparse_vector["indices"]),
            "max_value": max(sparse_vector["values"]) if sparse_vector["values"] else 0,
            "sample_indices": sparse_vector["indices"][:10],  # First 10 indices
            "sample_values": sparse_vector["values"][:10]      # First 10 values
        }