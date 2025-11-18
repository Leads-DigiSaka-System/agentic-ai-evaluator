from typing import List, Dict, Any, Optional, Tuple
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from src.database.insert import qdrant_client
from src.utils.clean_logger import get_clean_logger

# Import our custom retrievers
from src.database.dense_retriever import QdrantDenseRetriever
from src.database.sparse_retriever import QdrantSparseRetriever


class LangChainHybridSearch:
    """
    Hybrid search system that combines semantic and keyword search for optimal results.
    
    This class uses LangChain's EnsembleRetriever to automatically weight and combine
    results from both dense (semantic similarity) and sparse (keyword matching) retrievers.
    
    Why Hybrid Search?
    - Dense retriever: Great for understanding meaning and context
    - Sparse retriever: Excellent for exact terms and specific keywords
    - Combined: Best of both worlds for comprehensive search
    """
    
    def __init__(
        self, 
        dense_weight: float = 0.7, 
        sparse_weight: float = 0.3,
        search_limit_per_retriever: int = 10
    ):
        """
        Initialize hybrid search with configurable parameters.
        
        Args:
            dense_weight: Weight for semantic similarity (0.0 to 1.0)
                         Higher = more focus on meaning and context
            sparse_weight: Weight for keyword matching (0.0 to 1.0)
                          Higher = more focus on exact terms
            search_limit_per_retriever: How many results each retriever should fetch
        
        Note: Weights don't need to sum to 1.0, they're relative importance
        """
        # Validate weights
        if dense_weight < 0 or sparse_weight < 0:
            raise ValueError("Weights must be non-negative")
        if dense_weight == 0 and sparse_weight == 0:
            raise ValueError("At least one weight must be positive")
        
        # Store configuration
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.search_limit = search_limit_per_retriever
        
        # Get clients and encoders from existing setup
        self._initialize_components()
        
        # Create the hybrid retriever
        self._create_ensemble_retriever()
    
    def _initialize_components(self):
        """Initialize Qdrant client and encoders from your existing setup."""
        self.client = qdrant_client.client
        self.collection_name = qdrant_client.collection_name
        self.dense_encoder = qdrant_client.dense_encoder
        self.sparse_encoder = qdrant_client.sparse_encoder
        self.dense_name = qdrant_client.dense_vector_name
        self.sparse_name = qdrant_client.sparse_vector_name
    
    def _create_ensemble_retriever(self):
        """Create and configure the ensemble retriever with both dense and sparse retrievers."""
        # Create individual retrievers
        self.dense_retriever = QdrantDenseRetriever(
            client=self.client,
            collection_name=self.collection_name,
            dense_encoder=self.dense_encoder,
            vector_name=self.dense_name,
            search_limit=self.search_limit
        )
        
        self.sparse_retriever = QdrantSparseRetriever(
            client=self.client,
            collection_name=self.collection_name,
            sparse_encoder=self.sparse_encoder,
            vector_name=self.sparse_name,
            search_limit=self.search_limit
        )
        
        # Combine them with LangChain's EnsembleRetriever
        self.hybrid_retriever = EnsembleRetriever(
            retrievers=[self.dense_retriever, self.sparse_retriever],
            weights=[self.dense_weight, self.sparse_weight]
        )
    
    def _format_results(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """
        Format LangChain documents into standardized result format.
        
        Args:
            documents: List of LangChain documents
            
        Returns:
            List of formatted search results
        """
        formatted_results = []
        for doc in documents:
            result = {
                "id": doc.metadata.get("id", ""),
                "score": doc.metadata.get("score", 0.0),
                "content": doc.page_content,
                "form_id": doc.metadata.get("form_id", ""),
                "form_title": doc.metadata.get("form_title", ""),
                "form_type": doc.metadata.get("form_type", ""),
                "date_of_insertion": doc.metadata.get("date_of_insertion", ""),
                "retriever_type": doc.metadata.get("retriever_type", "hybrid")
            }
            formatted_results.append(result)
        return formatted_results
    
    async def search(self, query: str, top_k: int = 5, user_id: str = None) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using both semantic and keyword matching with user_id filtering.
        
        This is your main search function that:
        1. Uses dense retriever to find semantically similar documents
        2. Uses sparse retriever to find keyword matches
        3. Combines and ranks results using configured weights
        4. Filters results by user_id for data isolation
        
        Args:
            query: Search query string
            top_k: Number of top results to return
            user_id: Optional user ID - if provided, only returns results belonging to that user
            
        Returns:
            List of search results with scores and metadata, sorted by relevance (filtered by user_id if provided)
        """
        try:
            # Use LangChain's ensemble retriever for automatic fusion
            # Wrapped in thread pool for async compatibility
            import asyncio
            loop = asyncio.get_event_loop()
            documents = await loop.run_in_executor(
                None, 
                self.hybrid_retriever.get_relevant_documents, 
                query
            )
            
            # ✅ Filter by user_id first (for data isolation)
            if user_id:
                documents = [doc for doc in documents if doc.metadata.get("user_id") == user_id]
            
            # Take only the top_k results
            documents = documents[:top_k]
            
            # Format results to match your original output format
            return self._format_results(documents)
            
        except Exception as e:
            logger = get_clean_logger(__name__)
            logger.db_error("hybrid search", str(e))
            return []
    
    def search_with_custom_weights(
        self, 
        query: str, 
        top_k: int = 5,
        dense_weight: float = 0.7, 
        sparse_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Perform search with custom weights without changing the instance configuration.
        
        Useful when you want to experiment with different weight combinations
        for specific queries without modifying the main searcher.
        
        Args:
            query: Search query string
            top_k: Number of results to return
            dense_weight: Temporary weight for semantic search
            sparse_weight: Temporary weight for keyword search
            
        Returns:
            List of search results with scores and metadata
        """
        # Create temporary ensemble retriever with custom weights
        temp_retriever = EnsembleRetriever(
            retrievers=[self.dense_retriever, self.sparse_retriever],
            weights=[dense_weight, sparse_weight]
        )
        
        # Perform search with temporary configuration
        documents = temp_retriever.get_relevant_documents(query)
        documents = documents[:top_k]
        
        # Format results using shared method
        return self._format_results(documents)
    
    async def compare_retrievers(self, query: str, top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Compare results from each retriever individually (useful for debugging).
        
        This helps you understand:
        - What dense retriever finds (semantic matches)
        - What sparse retriever finds (keyword matches)
        - How the combination differs from individual results
        
        Args:
            query: Search query string
            top_k: Number of results per retriever
            
        Returns:
            Dictionary with separate results from each retriever and combined results
        """
        results = {}
        
        try:
            # Get results from dense retriever only (wrapped in thread pool for async)
            import asyncio
            loop = asyncio.get_event_loop()
            dense_docs = await loop.run_in_executor(
                None,
                lambda: self.dense_retriever.get_relevant_documents(query)[:top_k]
            )
            results["dense_only"] = [
                {
                    "id": doc.metadata.get("id", ""),
                    "score": doc.metadata.get("score", 0.0),
                    "content": doc.page_content[:200] + "...",  # Truncate for comparison
                    "form_title": doc.metadata.get("form_title", "")
                }
                for doc in dense_docs
            ]
            
            # Get results from sparse retriever only (wrapped in thread pool for async)
            sparse_docs = await loop.run_in_executor(
                None,
                lambda: self.sparse_retriever.get_relevant_documents(query)[:top_k]
            )
            results["sparse_only"] = [
                {
                    "id": doc.metadata.get("id", ""),
                    "score": doc.metadata.get("score", 0.0),
                    "content": doc.page_content[:200] + "...",  # Truncate for comparison
                    "form_title": doc.metadata.get("form_title", "")
                }
                for doc in sparse_docs
            ]
            
            # Get hybrid results (now async)
            hybrid_results = await self.search(query, top_k)
            results["hybrid"] = [
                {
                    "id": result["id"],
                    "score": result["score"],
                    "content": result["content"][:200] + "...",  # Truncate for comparison
                    "form_title": result["form_title"]
                }
                for result in hybrid_results
            ]
            
        except Exception as e:
            logger = get_clean_logger(__name__)
            logger.db_error("retriever comparison", str(e))
            results = {"error": str(e)}
        
        return results
    
    def update_weights(self, dense_weight: float, sparse_weight: float):
        """
        Update the default weights for the hybrid retriever.
        
        Args:
            dense_weight: New weight for semantic search
            sparse_weight: New weight for keyword search
        """
        if dense_weight < 0 or sparse_weight < 0:
            raise ValueError("Weights must be non-negative")
        if dense_weight == 0 and sparse_weight == 0:
            raise ValueError("At least one weight must be positive")
        
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        
        # Recreate the ensemble retriever with new weights
        self._create_ensemble_retriever()
    
    def get_configuration(self) -> Dict[str, Any]:
        """
        Get current configuration and system information.
        
        Returns:
            Dictionary with current settings and system info
        """
        return {
            "weights": {
                "dense_weight": self.dense_weight,
                "sparse_weight": self.sparse_weight
            },
            "collection_info": {
                "collection_name": self.collection_name,
                "dense_vector_name": self.dense_name,
                "sparse_vector_name": self.sparse_name
            },
            "retriever_limits": {
                "search_limit_per_retriever": self.search_limit
            },
            "encoders": {
                "dense_encoder": type(self.dense_encoder).__name__,
                "sparse_encoder": type(self.sparse_encoder).__name__
            }
        }

    async def search_balanced(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
            """Quick balanced search with score normalization"""
            
            # Get separate results - wrapped in thread pool for async compatibility
            import asyncio
            loop = asyncio.get_event_loop()
            dense_docs = await loop.run_in_executor(None, lambda: self.dense_retriever.invoke(query)[:5])
            sparse_docs = await loop.run_in_executor(None, lambda: self.sparse_retriever.invoke(query)[:5])
            
            # Simple rank-based scoring (avoids score magnitude issues)
            all_results = []
            
            # Add dense results with rank scores
            for i, doc in enumerate(dense_docs):
                doc.metadata["final_score"] = (5-i) * self.dense_weight  # 5,4,3,2,1
                doc.metadata["retriever_type"] = "dense"
                all_results.append(doc)
            
            # Add sparse results with rank scores  
            for i, doc in enumerate(sparse_docs):
                doc_id = doc.metadata.get("id")
                rank_score = (5-i) * self.sparse_weight
                
                # Check if already exists from dense
                existing = next((d for d in all_results if d.metadata.get("id") == doc_id), None)
                if existing:
                    existing.metadata["final_score"] += rank_score
                    existing.metadata["retriever_type"] = "hybrid"
                else:
                    doc.metadata["final_score"] = rank_score
                    doc.metadata["retriever_type"] = "sparse"  
                    all_results.append(doc)
            
            # Sort by final score
            all_results.sort(key=lambda x: x.metadata["final_score"], reverse=True)
            return self._format_results(all_results[:top_k])


# Convenience function for quick setup
def create_hybrid_search(
    dense_weight: float = 0.7, 
    sparse_weight: float = 0.3
) -> LangChainHybridSearch:
    """
    Quick factory function to create a hybrid search instance.
    
    Args:
        dense_weight: Weight for semantic similarity
        sparse_weight: Weight for keyword matching
        
    Returns:
        Configured LangChainHybridSearch instance
    """
    return LangChainHybridSearch(dense_weight, sparse_weight)