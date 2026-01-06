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
    def _get_relevant_documents(self, query: str, cooperative: Optional[str] = None, applicant: Optional[str] = None, location: Optional[str] = None, limit: Optional[int] = None) -> List[Document]:
        """
        Retrieve documents using dense vector search with optional cooperative filtering.
        Same cooperative can see all data within that cooperative.
        
        Args:
            query: Search query string
            cooperative: Optional cooperative ID for cooperative-specific access - filters at database level
            limit: Optional limit override (if None, uses self.search_limit)
            
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
                "cooperative_filtered": cooperative is not None
            })
            
            # ORIGINAL CODE: Encode query to vector
            query_vector = self.dense_encoder.encode([query])[0]
            
            # ✅ NEW: Log vector details
            update_trace_with_metrics({
                "vector_dimension": len(query_vector)
            })
            
            # ✅ SECURITY FIX: Build Qdrant filter at database level for cooperative isolation
            # This ensures data security and better performance
            # Same cooperative can see all data within that cooperative
            # Also support applicant filtering for exact name matching
            # NOTE: Qdrant MatchValue is case-sensitive, so we do post-filtering for case-insensitive matching
            # This handles cases where database has "Leads" but header sends "leads" or "LEADS"
            query_filter = None
            filter_conditions = []
            
            # Store cooperative for post-filtering (case-insensitive)
            # We do post-filtering instead of Qdrant filter to handle case sensitivity
            cooperative_for_filtering = None
            if cooperative:
                cooperative_for_filtering = cooperative.strip()
                self.logger.debug(f"Will filter by cooperative in post-processing (case-insensitive): {cooperative_for_filtering}")
            
            # ✅ Add applicant and location filters - but use semantic search + post-filtering for better flexibility
            # Qdrant filters are case-sensitive, so we'll do semantic search first
            # and filter by applicant/location in code for case-insensitive matching
            # Store filters for post-filtering
            applicant_for_filtering = None
            location_for_filtering = None
            
            if applicant:
                applicant_for_filtering = applicant.strip().lower()  # Normalize for case-insensitive matching
                self.logger.debug(f"Will filter by applicant in post-processing: {applicant_for_filtering}")
            
            if location:
                location_for_filtering = location.strip().lower()  # Normalize for case-insensitive matching
                self.logger.debug(f"Will filter by location in post-processing: {location_for_filtering}")
            
            if filter_conditions:
                query_filter = models.Filter(must=filter_conditions)
            
            # ✅ Use provided limit or fallback to instance limit
            # If filtering by applicant, location, or cooperative (post-filtering), increase limit to get more candidates
            base_limit = limit if limit is not None else self.search_limit
            # If we're doing post-filtering (case-insensitive), we need more candidates
            # Note: cooperative_for_filtering means we'll do post-filtering (case-insensitive check)
            has_post_filter = applicant_for_filtering or location_for_filtering or cooperative_for_filtering
            search_limit = base_limit * 5 if has_post_filter else base_limit  # Get 5x more if post-filtering
            
            # ✅ Search with database-level filtering for security and performance
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=(self.vector_name, query_vector),
                query_filter=query_filter,  # ✅ Filter at DB level - secure and efficient
                limit=search_limit,  # ✅ Use parameter limit to avoid race conditions
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
            exact_matches = []  # Store exact matches separately to boost them
            
            for result in search_results:
                # Extract payload for filtering
                payload = result.payload or {}
                
                # ✅ Post-filter by cooperative (case-insensitive with partial matching)
                # Handles cases like "Leads" vs "Leads Agri" - matches if one contains the other
                if cooperative_for_filtering:
                    doc_cooperative = payload.get("cooperative", "").strip()
                    query_coop_lower = cooperative_for_filtering.lower()
                    doc_coop_lower = doc_cooperative.lower()
                    
                    # Normalize: remove common suffixes/prefixes for matching
                    # "Leads Agri" -> "Leads", "Leads" -> "Leads"
                    def normalize_coop(name):
                        name = name.lower().strip()
                        # Remove common suffixes
                        for suffix in [" agri", " agriculture", " cooperative", " coop"]:
                            if name.endswith(suffix):
                                name = name[:-len(suffix)].strip()
                        return name
                    
                    query_coop_norm = normalize_coop(cooperative_for_filtering)
                    doc_coop_norm = normalize_coop(doc_cooperative)
                    
                    # Match if normalized names match, or if one contains the other
                    if (query_coop_norm != doc_coop_norm and 
                        query_coop_norm not in doc_coop_norm and 
                        doc_coop_norm not in query_coop_norm):
                        self.logger.debug(
                            f"Document filtered out by cooperative post-processing: "
                            f"'{doc_cooperative}' (normalized: '{doc_coop_norm}') != "
                            f"'{cooperative_for_filtering}' (normalized: '{query_coop_norm}')"
                        )
                        continue  # Skip this document
                
                # ✅ Post-filter by applicant or location if specified (case-insensitive with fuzzy matching)
                import re
                def normalize_name(name):
                    return re.sub(r'[^\w\s]', '', name.lower().strip())
                
                applicant_match = False
                location_match = False
                boost_amount = 0.0
                match_flags = {}
                
                # Check applicant filter
                if applicant_for_filtering:
                    applicant_in_doc = payload.get("applicant", "").strip().lower()
                    applicant_query_norm = normalize_name(applicant_for_filtering)
                    applicant_doc_norm = normalize_name(applicant_in_doc)
                    
                    # Exact match after normalization
                    if applicant_query_norm == applicant_doc_norm:
                        applicant_match = True
                        boost_amount = max(boost_amount, 0.2)  # Higher boost for exact
                        match_flags["exact_applicant_match"] = True
                    else:
                        # Fuzzy match: check if all words match
                        query_words = set(applicant_query_norm.split())
                        doc_words = set(applicant_doc_norm.split())
                        if len(query_words) > 0:
                            match_ratio = len(query_words.intersection(doc_words)) / len(query_words)
                            if match_ratio >= 0.8:  # 80%+ words match
                                applicant_match = True
                                boost_amount = max(boost_amount, 0.1)  # Smaller boost for fuzzy
                                match_flags["fuzzy_applicant_match"] = True
                
                # Check location filter
                if location_for_filtering:
                    location_in_doc = payload.get("location", "").strip().lower()
                    location_query_norm = normalize_name(location_for_filtering)
                    location_doc_norm = normalize_name(location_in_doc)
                    
                    # Substring match (handles "Zambales" in "PI, DIRITA, IBA, ZAMBALES")
                    if location_query_norm in location_doc_norm or location_doc_norm in location_query_norm:
                        location_match = True
                        boost_amount = max(boost_amount, 0.2)  # Higher boost for substring match
                        match_flags["location_match"] = True
                    else:
                        # Word-level matching
                        location_query_words = set(location_query_norm.split())
                        location_doc_words = set(location_doc_norm.split())
                        if len(location_query_words) > 0:
                            match_ratio = len(location_query_words.intersection(location_doc_words)) / len(location_query_words)
                            if match_ratio >= 0.7:  # 70%+ words match
                                location_match = True
                                boost_amount = max(boost_amount, 0.1)  # Smaller boost for fuzzy
                                match_flags["location_fuzzy_match"] = True
                
                # Determine if we should include this document
                # If both filters specified, both must match
                # If only one filter specified, that one must match
                if applicant_for_filtering and location_for_filtering:
                    # Both filters - both must match
                    if not (applicant_match and location_match):
                        self.logger.debug(
                            f"Skipping document - filter mismatch: "
                            f"applicant_match={applicant_match}, location_match={location_match}"
                        )
                        continue
                elif applicant_for_filtering:
                    # Only applicant filter - must match
                    if not applicant_match:
                        self.logger.debug(
                            f"Skipping document - applicant mismatch: "
                            f"'{payload.get('applicant', '')}' != '{applicant_for_filtering}'"
                        )
                        continue
                elif location_for_filtering:
                    # Only location filter - must match
                    if not location_match:
                        self.logger.debug(
                            f"Skipping document - location mismatch: "
                            f"'{payload.get('location', '')}' doesn't contain '{location_for_filtering}'"
                        )
                        continue
                
                # If we have matches, add to exact_matches with boost
                if boost_amount > 0:
                    doc = Document(
                        page_content=payload.get("summary_text", ""),
                        metadata={
                            **payload,
                            "score": min(1.0, result.score + boost_amount),
                            "id": result.id,
                            **match_flags
                        }
                    )
                    exact_matches.append(doc)
                    continue
                
                # No applicant filter - add all documents
                doc = Document(
                    page_content=payload.get("summary_text", ""),
                    metadata={
                        **payload,  # Include all payload fields (including user_id if present)
                        "score": result.score,
                        "id": result.id
                    }
                )
                documents.append(doc)
            
            # Put exact matches first, then other documents
            documents = exact_matches + documents
            
            # ORIGINAL CODE: Log and return
            self.logger.db_query("dense search", f"query: '{query[:50]}...'", len(documents))
            return documents
            
        except Exception as e:
            # ✅ NEW: Log error to trace (1 new line added)
            update_trace_with_error(e, {"operation": "dense_retrieval", "collection": self.collection_name})
            # ORIGINAL CODE: Log error
            self.logger.db_error("dense search", str(e))
            raise
    
    async def _aget_relevant_documents(self, query: str, cooperative: Optional[str] = None, applicant: Optional[str] = None, location: Optional[str] = None, limit: Optional[int] = None) -> List[Document]:
        """
        Async version of _get_relevant_documents.
        
        Runs the synchronous method in a thread pool executor to avoid blocking
        the event loop during Qdrant operations and encoding.
        
        Args:
            query: Search query string
            cooperative: Optional cooperative ID for cooperative-specific access - filters at database level
            limit: Optional limit override (if None, uses self.search_limit)
            
        Returns:
            List of Document objects with metadata and scores
        """
        import asyncio
        loop = asyncio.get_event_loop()
        # Run blocking operations (encoding + Qdrant search) in thread pool
        # ✅ Pass limit as parameter to avoid race conditions with shared state
        return await loop.run_in_executor(None, self._get_relevant_documents, query, cooperative, applicant, location, limit)
    
    def __repr__(self) -> str:
        return (f"QdrantDenseRetriever(collection='{self.collection_name}', "
                f"vector='{self.vector_name}', limit={self.search_limit})")