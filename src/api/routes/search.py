from fastapi import APIRouter, HTTPException, Request, Depends, Header, Query
from pydantic import BaseModel, validator, Field
from src.infrastructure.vector_store.hybrid_search import LangChainHybridSearch
from src.infrastructure.vector_store.analysis_search import analysis_searcher
from src.shared.limiter_config import limiter
from src.core import constants
from src.core.errors import ProcessingError, ValidationError
from src.shared.logging.clean_logger import get_clean_logger
from src.monitoring.trace.langfuse_helper import (
    is_langfuse_enabled,
    update_trace_with_metrics,
    update_trace_with_error,
)
from src.monitoring.scores.search_score import log_search_scores
from src.monitoring.session.langfuse_session_helper import (
    generate_session_id,
    propagate_session_id,
)

if is_langfuse_enabled():
    from langfuse import observe, get_client
else:
    def observe(**kwargs):
        def decorator(fn):
            return fn
        return decorator
    def get_client():
        return None
from src.api.deps.cooperative_context import get_cooperative
from src.shared.validation import validate_search_query
from typing import Optional

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
@observe(name="analysis_search")
async def analysis_search(
    request: Request,  #  REQUIRED: For SlowAPI rate limiter
    body: AnalysisSearchRequest,  #  RENAMED: Your request body (was 'request')
    cooperative: str = Depends(get_cooperative),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    session_id: Optional[str] = Query(None, description="Optional session ID for Langfuse grouping"),
):
    try:
        # Validate and sanitize query (max 500, min 1) — raises ValidationError on failure
        query = validate_search_query(body.query, max_length=500, min_length=1)

        # Session ID for Langfuse Sessions/Users: use query param or generate (propagate to all observations)
        sid = (session_id and session_id.strip())[:200] if session_id and session_id.strip() else generate_session_id(prefix=f"search_{cooperative}")
        uid = (x_user_id and x_user_id.strip())[:200] if x_user_id and x_user_id.strip() else ""

        with propagate_session_id(sid, user_id=uid or None):
            # Langfuse: set trace attributes (tags) and ensure user_id/session_id on trace
            langfuse = get_client() if is_langfuse_enabled() else None
            if langfuse:
                try:
                    attrs = {"tags": ["search", "analysis_search", "api"]}
                    if uid:
                        attrs["user_id"] = uid
                    attrs["session_id"] = sid
                    langfuse.update_current_trace(**attrs)
                except Exception as e:
                    logger.debug(f"Could not add tags to trace: {e}")

            # ✅ Search with cooperative filtering only - same cooperative can see all data
            results = await analysis_searcher.search(
                query=query,
                top_k=body.top_k,
                cooperative=cooperative,
            )

            # Calculate search quality metrics for metadata
            has_results = len(results) > 0
            results_count = len(results)

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

            update_trace_with_metrics({
                "query_length": len(query),
                "top_k_requested": body.top_k,
                "results_returned": results_count,
                "has_results": has_results,
                "avg_relevance_score": avg_relevance if has_results else 0.0,
                "avg_data_quality": avg_data_quality if has_results else 0.0,
                "search_efficiency": search_efficiency,
                "cooperative": cooperative,
            })

            log_search_scores(results, body.top_k)

            if not results:
                return {
                    "message": "No relevant analysis results found. Try using more specific keywords related to products, crops, or locations.",
                    "query": query,
                    "results": [],
                    "filtered": True,
                }

            return {
                "query": query,
                "total_results": results_count,
                "results": results,
            }

    except Exception as e:
        #  Log error to trace
        error_msg = str(e)
        import traceback
        logger.error(f"Analysis search failed: {error_msg}\n{traceback.format_exc()}")
        update_trace_with_error(e, {
            "endpoint": "analysis_search",
            "query": body.query[:100] if body.query else "N/A"
        })
        raise HTTPException(
            status_code=500, 
            detail=f"Analysis search failed: {error_msg}. Please check the logs for more details."
        )