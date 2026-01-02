from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from qdrant_client import QdrantClient
import json

from src.utils.config import QDRANT_LOCAL_URI, QDRANT_COLLECTION_ANALYSIS, QDRANT_API_KEY
from src.generator.encoder import DenseEncoder
from src.database.analysis_dense_retriever import QdrantDenseRetriever
from src.utils.clean_logger import get_clean_logger
from src.utils import constants
from src.monitoring.trace.langfuse_helper import observe_operation, update_trace_with_metrics, update_trace_with_error


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
            self.logger = get_clean_logger(__name__)
            # Initialize QdrantClient with optional API key for Qdrant Cloud
            # Increased timeout for remote Qdrant servers (60 seconds)
            if QDRANT_API_KEY:
                self.client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=60)
                self.logger.info("AnalysisHybridSearch: Initialized with API key (Qdrant Cloud)")
            else:
                self.client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=60)
                self.logger.info("AnalysisHybridSearch: Initialized without API key (local Qdrant)")
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
            self.logger.storage_start("AnalysisHybridSearch", f"collection: {self.collection_name}")
            
        except Exception as e:
            self.logger.storage_error("AnalysisHybridSearch initialization", str(e))
            raise
    
    @observe_operation(name="analysis_hybrid_search")
    async def search(self, query: str, top_k: int = 5, cooperative: str = None, applicant: str = None, location: str = None) -> List[Dict[str, Any]]:
        """
        Search for relevant analysis documents with cooperative filtering for data isolation.
        Same cooperative can see all data within that cooperative.
        
        Args:
            query: Search query string
            top_k: Number of top results to return (default: 5)
            cooperative: Optional cooperative ID - if provided, only returns results belonging to that cooperative
            
        Returns:
            List of formatted analysis results with metadata (filtered by cooperative if provided)
            
        Example:
            >>> results = searcher.search("rice fertilizer demo", top_k=3, cooperative="coop001")
        """
        if not query or not query.strip():
            self.logger.warning("Empty search query provided")
            return []
        
        if top_k <= 0:
            self.logger.warning(f"Invalid top_k value: {top_k}. Using default: 5")
            top_k = 5
        
        try:
            # ✅ Adjust search_limit to ensure we get enough results after user_id filtering
            # If filtering by user_id, we might need to retrieve more to get top_k results
            # But since we filter at Qdrant level now, we can use top_k directly
            effective_limit = top_k
            
            # ✅ Log search parameters
            update_trace_with_metrics({
                "search_query": query[:100],
                "top_k": top_k,
                "effective_limit": effective_limit,
                "cooperative": cooperative,
                "collection": self.collection_name
            })
            
            # ✅ SECURITY FIX: Pass limit as parameter to avoid race conditions
            # Each request has its own limit parameter, no shared state modification
            # This ensures concurrent searches don't interfere with each other
            documents = await self.dense_retriever._aget_relevant_documents(
                query, 
                cooperative=cooperative,
                applicant=applicant,  # ✅ Add applicant filter support
                location=location,  # ✅ Add location filter support
                limit=top_k  # ✅ Pass limit as parameter - thread-safe!
            )
            
            # ✅ Log retrieval results
            update_trace_with_metrics({
                "documents_retrieved": len(documents),
                "documents_before_topk": len(documents),
                "cooperative_filtered": cooperative is not None,
                "filtering_method": "database_level"  # Track that we're using DB-level filtering
            })
            
            # ✅ Filter documents by score threshold (adaptive)
            # Check if we have exact filter (applicant, location) for adaptive threshold
            has_exact_filter = applicant is not None or location is not None
            
            try:
                # Try strict threshold first (adaptive based on query type)
                filtered_documents = self._filter_relevant_documents(
                    documents, query, strict=True, has_exact_filter=has_exact_filter
                )
                
                # If no results with strict threshold, try more lenient
                if len(filtered_documents) == 0 and len(documents) > 0:
                    self.logger.info(
                        f"No results with strict threshold, trying lenient threshold "
                        f"for query: '{query[:50]}...'"
                    )
                    filtered_documents = self._filter_relevant_documents(
                        documents, query, strict=False, has_exact_filter=has_exact_filter
                    )
            except Exception as filter_error:
                self.logger.db_error("filter documents", str(filter_error))
                # If filtering fails, use original documents (fallback)
                filtered_documents = documents
            
            # ✅ Log filtering results
            update_trace_with_metrics({
                "documents_after_filtering": len(filtered_documents),
                "documents_filtered_out": len(documents) - len(filtered_documents),
                "min_score_threshold": constants.MIN_SEARCH_SCORE_THRESHOLD
            })
            
            # Format and return top-k results
            try:
                formatted_results = self._format_analysis_results(filtered_documents[:top_k])
            except Exception as format_error:
                self.logger.db_error("format results", str(format_error))
                # Return empty list if formatting fails
                formatted_results = []
            
            # ✅ Log final results
            update_trace_with_metrics({
                "formatted_results_count": len(formatted_results),
                "avg_score": sum(r.get("score", 0) for r in formatted_results) / len(formatted_results) if formatted_results else 0
            })
            
            self.logger.db_query("analysis search", f"query: '{query[:50]}...'", len(formatted_results))
            return formatted_results
            
        except ValueError as e:
            update_trace_with_error(e, {"operation": "analysis_search", "error_type": "validation"})
            self.logger.db_error("analysis search", str(e))
            return []
        except Exception as e:
            update_trace_with_error(e, {"operation": "analysis_search", "error_type": "unexpected"})
            self.logger.db_error("analysis search", str(e))
            return []
    
    def _boost_score_for_exact_match(self, doc: Document, query: str, original_score: float) -> float:
        """
        Boost score if there's an exact or near-exact match in key fields.
        This helps with name searches where semantic similarity might be lower.
        
        Args:
            doc: Document to check
            query: Original search query
            original_score: Original similarity score from embedding
            
        Returns:
            Boosted score if exact match found, otherwise original score
        """
        query_lower = query.lower().strip()
        
        # Check key fields for exact or near-exact matches
        searchable_fields = {
            "cooperator": doc.metadata.get("cooperator", "").lower(),
            "product": doc.metadata.get("product", "").lower(),
            "location": doc.metadata.get("location", "").lower(),
            "crop": doc.metadata.get("crop", "").lower(),
            "applicant": doc.metadata.get("applicant", "").lower(),
        }
        
        # Check for exact match or substring match (case-insensitive)
        # This handles "Zambales" matching "PI, DIRITA, IBA, ZAMBALES"
        for field_name, field_value in searchable_fields.items():
            # Exact match
            if query_lower == field_value:
                boost = 0.20  # Higher boost for exact match
                boosted_score = min(1.0, original_score + boost)
                self.logger.debug(
                    f"Exact match found in {field_name}: '{query_lower}' -> "
                    f"score boosted from {original_score:.3f} to {boosted_score:.3f}"
                )
                return boosted_score
            
            # Substring match (query in field or field in query)
            # This is important for locations like "Zambales" in "PI, DIRITA, IBA, ZAMBALES"
            if query_lower in field_value or field_value in query_lower:
                # Boost score for substring match
                boost = 0.15  # Add 0.15 to score for substring match
                boosted_score = min(1.0, original_score + boost)
                self.logger.debug(
                    f"Substring match found in {field_name}: '{query_lower}' in '{field_value[:50]}...' -> "
                    f"score boosted from {original_score:.3f} to {boosted_score:.3f}"
                )
                return boosted_score
        
        # Check for partial match (at least 70% of query words match)
        query_words = set(query_lower.split())
        if len(query_words) > 0:
            for field_name, field_value in searchable_fields.items():
                field_words = set(field_value.split())
                if len(field_words) > 0:
                    match_ratio = len(query_words.intersection(field_words)) / len(query_words)
                    if match_ratio >= 0.7:  # 70% of words match
                        boost = 0.10 * match_ratio  # Proportional boost
                        boosted_score = min(1.0, original_score + boost)
                        self.logger.debug(
                            f"Partial match ({match_ratio:.1%}) in {field_name}: "
                            f"score boosted from {original_score:.3f} to {boosted_score:.3f}"
                        )
                        return boosted_score
        
        return original_score
    
    def _is_name_query(self, query: str) -> bool:
        """
        Detect if query is likely a name search (applicant, location, etc.).
        
        Args:
            query: Search query string
            
        Returns:
            True if query looks like a name search
        """
        query_lower = query.lower().strip()
        
        # Check for name-like patterns (multiple capitalized words, common name patterns)
        name_indicators = [
            len(query.split()) >= 2,  # Multiple words
            any(word[0].isupper() for word in query.split() if word),  # Has capitals
            not any(keyword in query_lower for keyword in ['improvement', 'performance', 'analysis', 'demo', 'trial'])  # Not semantic query
        ]
        
        return all(name_indicators)
    
    def _get_adaptive_threshold(self, query: str, has_exact_filter: bool = False) -> float:
        """
        Get adaptive score threshold based on search type.
        
        - Exact filters (applicant, location): Lower threshold (0.5) - names need exact matching
        - Name queries: Medium threshold (0.6) - semantic similarity less reliable
        - Semantic queries: Standard threshold (0.75) - meaning-based matching
        
        Args:
            query: Search query string
            has_exact_filter: True if filtering by exact field (applicant, location)
            
        Returns:
            Adaptive threshold value (0.0-1.0)
        """
        if has_exact_filter:
            # Exact field filtering - lower threshold since we're already filtering
            return 0.5
        
        if self._is_name_query(query):
            # Name queries - medium threshold
            return 0.6
        
        # Default semantic search threshold
        try:
            return constants.MIN_SEARCH_SCORE_THRESHOLD
        except AttributeError:
            return 0.75
    
    def _filter_relevant_documents(self, documents: List[Document], query: str, strict: bool = True, has_exact_filter: bool = False) -> List[Document]:
        """
        Filter documents based on adaptive score threshold.
        
        Uses adaptive thresholds based on search type:
        - Exact matches: Lower threshold (0.5)
        - Name queries: Medium threshold (0.6)
        - Semantic queries: Standard threshold (0.75)
        
        Args:
            documents: List of Document objects from retriever
            query: Original search query (for logging purposes)
            strict: If True, use strict threshold, else use lenient
            has_exact_filter: True if filtering by exact field (applicant, location)
            
        Returns:
            Filtered list of documents that meet the score threshold
        """
        if not documents:
            return []
        
        # Get adaptive threshold
        base_threshold = self._get_adaptive_threshold(query, has_exact_filter)
        
        if strict:
            min_score = base_threshold
        else:
            # Use even more lenient threshold (reduce by 0.1)
            min_score = max(0.4, base_threshold - 0.1)
            self.logger.debug(f"Using lenient threshold: {min_score} (base: {base_threshold})")
        
        self.logger.debug(f"Using adaptive threshold: {min_score} (query type: {'name' if self._is_name_query(query) else 'semantic'}, exact_filter: {has_exact_filter})")
        
        filtered = []
        for doc in documents:
            try:
                # Get original score from embedding similarity
                original_score = doc.metadata.get("score", 0.0)
                
                # Ensure score is a number
                if not isinstance(original_score, (int, float)):
                    try:
                        original_score = float(original_score)
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid score type: {type(original_score)}, using 0.0")
                        original_score = 0.0
                
                # Boost score if there's an exact match (helps with name searches)
                boosted_score = self._boost_score_for_exact_match(doc, query, original_score)
                
                # Update document metadata with boosted score
                doc.metadata["score"] = boosted_score
                doc.metadata["original_score"] = original_score  # Keep original for reference
                
                if boosted_score >= min_score:
                    filtered.append(doc)
                else:
                    self.logger.debug(
                        f"Document filtered out: boosted_score {boosted_score:.3f} "
                        f"(original: {original_score:.3f}) < threshold {min_score}. "
                        f"Query: '{query[:50] if query else 'N/A'}...'"
                    )
            except Exception as e:
                # If there's an error processing a document, log and skip it
                self.logger.warning(f"Error processing document in filter: {str(e)}")
                continue
        
        # Sort by score descending (highest relevance first)
        try:
            filtered.sort(key=lambda x: float(x.metadata.get("score", 0.0)), reverse=True)
        except Exception as e:
            self.logger.warning(f"Error sorting filtered documents: {str(e)}")
            # Return unsorted if sorting fails
            pass
        
        return filtered
    
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
            
            # ✅ Helper function to safely extract nested data (handles both dict and JSON string for backward compatibility)
            def safe_extract_nested(field_value, default=None):
                """Extract nested data - handles both dict (new format) and JSON string (old format)"""
                if field_value is None:
                    return default if default is not None else {}
                
                # If already a dictionary, return as-is (new format)
                if isinstance(field_value, dict):
                    return field_value
                
                # If string, try to parse as JSON (old format - backward compatibility)
                if isinstance(field_value, str):
                    if not field_value or field_value == "{}":
                        return default if default is not None else {}
                    try:
                        return json.loads(field_value)
                    except (json.JSONDecodeError, TypeError):
                        self.logger.warning(f"Failed to parse JSON: {field_value[:100] if field_value else 'None'}...")
                        return default if default is not None else {}
                
                # Fallback
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
                "applicant": payload.get("applicant", ""),
                "form_type": payload.get("form_type", ""),
                
                # Performance Metrics
                "improvement_percent": float(payload.get("improvement_percent", 0.0)),
                "control_average": float(payload.get("control_average", 0.0)),
                "leads_average": float(payload.get("leads_average", 0.0)),
                "performance_significance": payload.get("performance_significance", ""),
                
                # Summaries
                "summary": payload.get("summary_text", ""),
                "executive_summary": payload.get("executive_summary", ""),
                
                # ✅ NEW: Direct dictionary access (with backward compatibility for old JSON strings)
                "graph_suggestions": safe_extract_nested(
                    payload.get("graph_suggestions"),
                    default={}
                ),
                "full_analysis": safe_extract_nested(
                    payload.get("full_analysis"),
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
            self.logger.db_error("get collection info", str(e))
            return {"status": "error", "error": str(e)}
    
    def __repr__(self) -> str:
        return (f"AnalysisHybridSearch(collection='{self.collection_name}', "
                f"search_limit={self.search_limit})")


# Global instance for easy import
analysis_searcher = AnalysisHybridSearch()