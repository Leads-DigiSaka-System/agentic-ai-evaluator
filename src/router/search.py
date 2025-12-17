from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, validator, Field
from src.database.hybrid_search import LangChainHybridSearch
from src.database.analysis_search import analysis_searcher 
from src.utils.limiter_config import limiter 
from src.utils import constants 
from src.utils.errors import ProcessingError, ValidationError
from src.utils.clean_logger import get_clean_logger
from src.utils.config import LANGFUSE_CONFIGURED
from src.monitoring.trace.langfuse_helper import (
    observe_operation, 
    update_trace_with_metrics, 
    update_trace_with_error,
    get_langfuse_client
)
from src.monitoring.scores.search_score import log_search_scores
from src.deps.cooperative_context import get_cooperative

router = APIRouter()
search_engine = LangChainHybridSearch()
logger = get_clean_logger(__name__)


class AnalysisSearchRequest(BaseModel):
    query: str
    top_k: int = constants.DEFAULT_SEARCH_TOP_K
    
    @validator('top_k')
    def validate_top_k(cls, v):
        if v > constants.MAX_SEARCH_TOP_K:
            raise ValueError(f"top_k cannot exceed {constants.MAX_SEARCH_TOP_K}")
        if v < 1:
            raise ValueError("top_k must be at least 1")
        return v


@router.post("/analysis-search")
@limiter.limit("60/minute")
@observe_operation(name="analysis_search")
async def analysis_search(
    request: Request,  #  REQUIRED: For SlowAPI rate limiter
    body: AnalysisSearchRequest,  #  RENAMED: Your request body (was 'request')
    cooperative: str = Depends(get_cooperative)
    # ✅ Removed user_id - same cooperative can see all data within that cooperative
):
    try:
        # Add tags to trace
        if LANGFUSE_CONFIGURED:
            try:
                client = get_langfuse_client()
                if client:
                    client.update_current_trace(
                        tags=["search", "analysis_search", "api"]
                    )
            except Exception as e:
                logger.debug(f"Could not add tags to trace: {e}")
        
        # ✅ Search with cooperative filtering only - same cooperative can see all data
        results = await analysis_searcher.search(
            query=body.query,  #  Changed from request.query to body.query
            top_k=body.top_k,   #  Changed from request.top_k to body.top_k
            cooperative=cooperative  # ✅ Filter results by cooperative only
        )
        
        # Calculate search quality metrics for metadata
        has_results = len(results) > 0
        results_count = len(results)
        
        # Calculate metrics for trace metadata (if needed)
        if has_results:
            relevance_scores = [r.get("score", 0.0) for r in results if isinstance(r.get("score"), (int, float))]
            data_quality_scores = [r.get("data_quality_score", 0.0) for r in results if isinstance(r.get("data_quality_score"), (int, float))]
            avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
            avg_data_quality = sum(data_quality_scores) / len(data_quality_scores) if data_quality_scores else 0.0
            search_efficiency = min(1.0, results_count / body.top_k) if body.top_k > 0 else 1.0
        else:
            avg_relevance = 0.0
            avg_data_quality = 0.0
            search_efficiency = 0.0
        
        # Log metrics to trace (including user_id for tracking)
        update_trace_with_metrics({
            "query_length": len(body.query),
            "top_k_requested": body.top_k,
            "results_returned": results_count,
            "has_results": has_results,
            "avg_relevance_score": avg_relevance if has_results else 0.0,
            "avg_data_quality": avg_data_quality if has_results else 0.0,
            "search_efficiency": search_efficiency,
            "cooperative": cooperative  # ✅ Track which cooperative performed the search
        })
        
        # Log scores using dedicated score module
        log_search_scores(results, body.top_k)
        
        if not results:
            return {
                "message": "No relevant analysis results found. Try using more specific keywords related to products, crops, or locations.",
                "query": body.query,  #  Changed
                "results": [],
                "filtered": True  # Indicates results were filtered by relevance threshold
            }
        
        return {
            "query": body.query,  #  Changed
            "total_results": results_count,
            "results": results
        }
        
    except Exception as e:
        #  Log error to trace
        error_msg = str(e)
        logger.error(f"Analysis search failed: {error_msg}", exc_info=True)
        update_trace_with_error(e, {
            "endpoint": "analysis_search",
            "query": body.query[:100] if body.query else "N/A"  #  Changed
        })
        raise HTTPException(
            status_code=500, 
            detail=f"Analysis search failed: {error_msg}. Please check the logs for more details."
        )