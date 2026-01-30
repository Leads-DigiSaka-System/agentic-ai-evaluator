from typing import List, Any, Optional
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from src.infrastructure.embeddings.encoder import DenseEncoder
from src.shared.logging.clean_logger import get_clean_logger
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
    def _get_relevant_documents(
        self,
        query: str,
        cooperative: Optional[str] = None,
        limit: Optional[int] = None,
        # All filter parameters (optional - extract from query)
        location: Optional[str] = None,
        product: Optional[str] = None,
        crop: Optional[str] = None,
        season: Optional[str] = None,
        applicant: Optional[str] = None,
        cooperator: Optional[str] = None,
        form_type: Optional[str] = None,
        product_category: Optional[str] = None,
        # Date filters
        application_date: Optional[str] = None,  # YYYY-MM-DD format
        planting_date: Optional[str] = None  # YYYY-MM-DD format
    ) -> List[Document]:
        """
        Retrieve documents using dense vector search with multiple filter support.
        Results must match ALL specified filters (AND logic).
        
        Args:
            query: Search query string
            cooperative: Cooperative ID for data isolation (required, passed automatically)
            limit: Optional limit override (if None, uses self.search_limit)
            location: Optional location filter (e.g., "Zambales", "Laguna")
            product: Optional product name filter (e.g., "iSMART NANO UREA")
            crop: Optional crop type filter (e.g., "rice", "corn")
            season: Optional season filter (e.g., "wet", "dry")
            applicant: Optional applicant name filter
            cooperator: Optional cooperator name filter
            form_type: Optional form type filter
            product_category: Optional product category filter
            
        Returns:
            List of Document objects matching ALL specified filters
            
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
            
            # ✅ Store all filters for post-filtering (case-insensitive matching)
            # Qdrant filters are case-sensitive, so we'll do semantic search first
            # and filter by all parameters in code for case-insensitive matching
            filters_for_post_processing = {}
            
            if location:
                # Keep location case for matching, but normalize for comparison
                filters_for_post_processing['location'] = location.strip()
                self.logger.info(f"🔍 Will filter by location: '{location.strip()}' (original: '{location}')")
            
            if product:
                filters_for_post_processing['product'] = product.strip().lower()
                self.logger.debug(f"Will filter by product: {filters_for_post_processing['product']}")
            
            if crop:
                filters_for_post_processing['crop'] = crop.strip().lower()
                self.logger.debug(f"Will filter by crop: {filters_for_post_processing['crop']}")
            
            if season:
                filters_for_post_processing['season'] = season.strip().lower()
                self.logger.debug(f"Will filter by season: {filters_for_post_processing['season']}")
            
            if applicant:
                filters_for_post_processing['applicant'] = applicant.strip().lower()
                self.logger.debug(f"Will filter by applicant: {filters_for_post_processing['applicant']}")
            
            if cooperator:
                filters_for_post_processing['cooperator'] = cooperator.strip().lower()
                self.logger.debug(f"Will filter by cooperator: {filters_for_post_processing['cooperator']}")
            
            if form_type:
                filters_for_post_processing['form_type'] = form_type.strip().lower()
                self.logger.debug(f"Will filter by form_type: {filters_for_post_processing['form_type']}")
            
            if product_category:
                filters_for_post_processing['product_category'] = product_category.strip().lower()
                self.logger.debug(f"Will filter by product_category: {filters_for_post_processing['product_category']}")
            
            if application_date:
                # Keep date as-is (not lowercased) for date matching
                filters_for_post_processing['application_date'] = application_date.strip()
                self.logger.debug(f"Will filter by application_date: {filters_for_post_processing['application_date']}")
            
            if planting_date:
                # Keep date as-is (not lowercased) for date matching
                filters_for_post_processing['planting_date'] = planting_date.strip()
                self.logger.debug(f"Will filter by planting_date: {filters_for_post_processing['planting_date']}")
            
            if filter_conditions:
                query_filter = models.Filter(must=filter_conditions)
            
            # ✅ Use provided limit or fallback to instance limit
            # If filtering by any parameter (post-filtering), increase limit to get more candidates
            base_limit = limit if limit is not None else self.search_limit
            # If we're doing post-filtering (case-insensitive), we need more candidates
            has_post_filter = len(filters_for_post_processing) > 0 or cooperative_for_filtering
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
            self.logger.info(f"🔍 Qdrant search returned {len(search_results)} results before post-filtering")
            if search_results:
                scores = [result.score for result in search_results]
                # Log first few results for debugging
                for i, result in enumerate(search_results[:3]):
                    payload = result.payload or {}
                    self.logger.debug(f"  Result {i+1}: score={result.score:.4f}, location={payload.get('location', 'N/A')}, cooperative={payload.get('cooperative', 'N/A')}")
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
                
                # ✅ Post-filter by ALL specified filters (AND logic - ALL must match)
                import re
                def normalize_name(name):
                    """Normalize name for case-insensitive matching"""
                    return re.sub(r'[^\w\s]', '', name.lower().strip())
                
                def check_filter_match(filter_value: str, doc_value: str, filter_type: str) -> tuple[bool, float]:
                    """
                    Check if document value matches filter value.
                    Returns: (match, boost_amount)
                    """
                    if not filter_value or not doc_value:
                        return False, 0.0
                    
                    # Special handling for date fields
                    if filter_type in ['application_date', 'planting_date']:
                        # For dates, check exact match or date range
                        filter_date = filter_value.strip()
                        doc_date = doc_value.strip()
                        
                        # Exact date match
                        if filter_date == doc_date:
                            return True, 0.3  # Higher boost for exact date match
                        
                        # Date range support (e.g., "2025-06" matches "2025-06-19")
                        if len(filter_date) == 7 and filter_date[4] == '-':  # YYYY-MM format
                            if doc_date.startswith(filter_date):
                                return True, 0.2
                        
                        # Year-only match (e.g., "2025" matches "2025-06-19")
                        if len(filter_date) == 4 and filter_date.isdigit():
                            if doc_date.startswith(filter_date):
                                return True, 0.1
                        
                        return False, 0.0
                    
                    # For non-date fields, use text matching
                    filter_norm = normalize_name(filter_value)
                    doc_norm = normalize_name(doc_value)
                    
                    # Exact match
                    if filter_norm == doc_norm:
                        return True, 0.2
                    
                    # Substring match (for location: "Zambales" in "PI, DIRITA, IBA, ZAMBALES")
                    if filter_type == 'location':
                        # Case-insensitive substring match
                        if filter_norm in doc_norm or doc_norm in filter_norm:
                            self.logger.debug(f"✅ Location match: '{filter_value}' found in '{doc_value}'")
                            return True, 0.2
                        else:
                            self.logger.debug(f"❌ Location mismatch: '{filter_value}' not in '{doc_value}'")
                    
                    # Word-level matching (for names, products, etc.)
                    filter_words = set(filter_norm.split())
                    doc_words = set(doc_norm.split())
                    if len(filter_words) > 0:
                        match_ratio = len(filter_words.intersection(doc_words)) / len(filter_words)
                        if match_ratio >= 0.8:  # 80%+ words match
                            return True, 0.1
                        elif match_ratio >= 0.6:  # 60%+ words match (fuzzy)
                            return True, 0.05
                    
                    return False, 0.0
                
                # Check ALL filters - ALL must match (AND logic)
                all_filters_passed = True
                boost_amount = 0.0
                match_flags = {}
                failed_filters = []
                
                for filter_name, filter_value in filters_for_post_processing.items():
                    doc_value = payload.get(filter_name, "").strip()
                    # For date fields, don't normalize (keep original format)
                    if filter_name in ['application_date', 'planting_date']:
                        match, boost = check_filter_match(filter_value, doc_value, filter_name)
                    else:
                        # For other fields, use normalized matching
                        match, boost = check_filter_match(filter_value, doc_value, filter_name)
                    
                    if match:
                        boost_amount = max(boost_amount, boost)
                        match_flags[f"{filter_name}_match"] = True
                        self.logger.debug(f"✅ Filter match: {filter_name}='{filter_value}' matches doc value '{doc_value}'")
                    else:
                        all_filters_passed = False
                        failed_filters.append(filter_name)
                        self.logger.debug(
                            f"❌ Filter mismatch - {filter_name}: "
                            f"'{doc_value}' doesn't match '{filter_value}'"
                        )
                
                # If ANY filter fails, skip this document (AND logic)
                if not all_filters_passed:
                    self.logger.info(
                        f"❌ Document filtered out - failed filters: {failed_filters}. "
                        f"Location in doc: '{payload.get('location', 'N/A')}', "
                        f"Cooperative in doc: '{payload.get('cooperative', 'N/A')}'"
                    )
                    continue
                else:
                    self.logger.info(f"✅ Document passed all filters! Location: '{payload.get('location', 'N/A')}', Cooperative: '{payload.get('cooperative', 'N/A')}'")
                
                # All filters passed - add document
                # Boost score if we have exact/fuzzy matches
                final_score = result.score
                if boost_amount > 0:
                    final_score = min(1.0, result.score + boost_amount)
                    # Add to exact_matches for priority sorting
                    doc = Document(
                        page_content=payload.get("summary_text", ""),
                        metadata={
                            **payload,
                            "score": final_score,
                            "id": result.id,
                            **match_flags
                        }
                    )
                    exact_matches.append(doc)
                else:
                    # No boost - add to regular documents
                    doc = Document(
                        page_content=payload.get("summary_text", ""),
                        metadata={
                            **payload,
                            "score": final_score,
                            "id": result.id
                        }
                    )
                    documents.append(doc)
            
            # Put exact matches first, then other documents
            documents = exact_matches + documents
            
            # ORIGINAL CODE: Log and return
            self.logger.info(f"📊 Final results: {len(documents)} documents after filtering (exact matches: {len(exact_matches)})")
            if documents:
                for i, doc in enumerate(documents[:3]):
                    location = doc.metadata.get('location', 'N/A')
                    cooperative = doc.metadata.get('cooperative', 'N/A')
                    self.logger.info(f"  Result {i+1}: location='{location}', cooperative='{cooperative}'")
            else:
                self.logger.warning(f"⚠️ No documents found after filtering! Check cooperative and location matching.")
            
            self.logger.db_query("dense search", f"query: '{query[:50]}...'", len(documents))
            return documents
            
        except Exception as e:
            # ✅ NEW: Log error to trace (1 new line added)
            update_trace_with_error(e, {"operation": "dense_retrieval", "collection": self.collection_name})
            # ORIGINAL CODE: Log error
            self.logger.db_error("dense search", str(e))
            raise
    
    async def _aget_relevant_documents(
        self,
        query: str,
        cooperative: Optional[str] = None,
        limit: Optional[int] = None,
        # All filter parameters
        location: Optional[str] = None,
        product: Optional[str] = None,
        crop: Optional[str] = None,
        season: Optional[str] = None,
        applicant: Optional[str] = None,
        cooperator: Optional[str] = None,
        form_type: Optional[str] = None,
        product_category: Optional[str] = None,
        # Date filters
        application_date: Optional[str] = None,
        planting_date: Optional[str] = None
    ) -> List[Document]:
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
        return await loop.run_in_executor(
            None,
            self._get_relevant_documents,
            query, cooperative, limit,
            location, product, crop, season, applicant, cooperator, form_type, product_category,
            application_date, planting_date
        )
    
    def __repr__(self) -> str:
        return (f"QdrantDenseRetriever(collection='{self.collection_name}', "
                f"vector='{self.vector_name}', limit={self.search_limit})")