from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from qdrant_client import QdrantClient
import logging
import json

from src.utils.config import QDRANT_LOCAL_URI, QDRANT_COLLECTION_ANALYSIS
from src.generator.encoder import DenseEncoder
from src.database.analysis_dense_retriever import QdrantDenseRetriever

logger = logging.getLogger(__name__)


class AnalysisHybridSearch:
    """
    Hybrid search system for agricultural analysis collection.
    
    Provides semantic search capabilities over stored analysis data
    using dense vector embeddings.
    
    Args:
        search_limit: Maximum number of results to retrieve (default: 10)
        
    Example:
        >>> searcher = AnalysisHybridSearch()
        >>> results = searcher.search("corn yield improvement", top_k=5)
        >>> for result in results:
        ...     print(result['product'], result['improvement_percent'])
    """
    
    def __init__(self, search_limit: int = 10):
        try:
            self.client = QdrantClient(url=QDRANT_LOCAL_URI)
            self.collection_name = QDRANT_COLLECTION_ANALYSIS
            self.dense_encoder = DenseEncoder()
            self.search_limit = search_limit
            
            # Initialize dense retriever for analysis collection
            self.dense_retriever = QdrantDenseRetriever(
                client=self.client,
                collection_name=self.collection_name,
                dense_encoder=self.dense_encoder,
                vector_name="dense",
                search_limit=search_limit
            )
            logger.info(f"✅ AnalysisHybridSearch initialized for '{self.collection_name}'")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize AnalysisHybridSearch: {str(e)}")
            raise
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant analysis documents.
        
        Args:
            query: Search query string
            top_k: Number of top results to return (default: 5)
            
        Returns:
            List of formatted analysis results with metadata
            
        Example:
            >>> results = searcher.search("rice fertilizer demo", top_k=3)
        """
        if not query or not query.strip():
            logger.warning("⚠️ Empty search query provided")
            return []
        
        if top_k <= 0:
            logger.warning(f"⚠️ Invalid top_k value: {top_k}. Using default: 5")
            top_k = 5
        
        try:
            # Perform dense vector search
            documents = self.dense_retriever.get_relevant_documents(query)
            
            # Format and return top-k results
            formatted_results = self._format_analysis_results(documents[:top_k])
            
            logger.info(f"🔍 Search completed: '{query[:50]}...' -> {len(formatted_results)} results")
            return formatted_results
            
        except ValueError as e:
            logger.error(f"❌ Invalid query: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"❌ Search error: {str(e)}")
            return []
    
    def _format_analysis_results(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """
        Format retrieved documents into structured analysis results.
        
        Extracts key fields from document metadata and ensures
        proper typing for downstream processing.
        
        Args:
            documents: List of Document objects from retriever
            
        Returns:
            List of dictionaries with formatted analysis data
        """
        results = []
        
        for doc in documents:
            payload = doc.metadata
            
            # ✅ Helper function to safely parse JSON strings
            def safe_json_parse(json_str: str, default=None):
                """Safely parse JSON string, return default if fails"""
                if not json_str or json_str == "{}":
                    return default if default is not None else {}
                try:
                    return json.loads(json_str)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse JSON: {json_str[:100]}...")
                    return default if default is not None else {}
            
            result = {
                # Identification
                "id": payload.get("form_id", ""),
                "score": float(payload.get("score", 0.0)),
                "report_number": payload.get("report_number", 1),
                
                # Basic Info
                "product": payload.get("product", ""),
                "location": payload.get("location", ""),
                "cooperator": payload.get("cooperator", ""),
                "crop": payload.get("crop", ""),
                "form_type": payload.get("form_type", ""),
                
                # Performance Metrics
                "improvement_percent": float(payload.get("improvement_percent", 0.0)),
                "control_average": float(payload.get("control_average", 0.0)),
                "leads_average": float(payload.get("leads_average", 0.0)),
                "performance_significance": payload.get("performance_significance", ""),
                
                # Summaries
                "summary": payload.get("summary_text", ""),
                "executive_summary": payload.get("executive_summary", ""),
                
                # ✅ FIXED: Parse JSON strings back to objects
                "graph_suggestions": safe_json_parse(
                    payload.get("graph_suggestions", "{}"),
                    default={}
                ),
                "full_analysis": safe_json_parse(
                    payload.get("full_analysis", "{}"),
                    default={}
                ),
                
                # Additional Context
                "product_category": payload.get("product_category", ""),
                "cooperator_feedback": payload.get("cooperator_feedback", ""),
                "data_quality_score": float(payload.get("data_quality_score", 0.0))
            }
            
            results.append(result)
        
        return results
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about the analysis collection.
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self.client.get_collection(self.collection_name)
            return {
                "collection_name": self.collection_name,
                "points_count": collection.points_count,
                "vector_size": collection.config.params.vectors.get("dense").size,
                "status": "ready"
            }
        except Exception as e:
            logger.error(f"❌ Failed to get collection info: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def __repr__(self) -> str:
        return (f"AnalysisHybridSearch(collection='{self.collection_name}', "
                f"search_limit={self.search_limit})")


# Global instance for easy import
analysis_searcher = AnalysisHybridSearch()