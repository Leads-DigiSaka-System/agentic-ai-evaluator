from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, validator, Field
from src.database.hybrid_search import LangChainHybridSearch
from src.database.analysis_search import analysis_searcher 
from src.utils.limiter_config import limiter 
from src.utils import constants 
from src.utils.errors import ProcessingError, ValidationError
from src.utils.clean_logger import get_clean_logger

router = APIRouter()
search_engine = LangChainHybridSearch()
logger = get_clean_logger(__name__)

class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    top_k: int = Field(constants.DEFAULT_SEARCH_TOP_K, ge=1, le=constants.MAX_SEARCH_TOP_K, description="Number of results")
    dense_weight: float = Field(constants.DENSE_WEIGHT_DEFAULT, ge=0.0, le=1.0, description="Dense vector weight")
    sparse_weight: float = Field(constants.SPARSE_WEIGHT_DEFAULT, ge=0.0, le=1.0, description="Sparse vector weight")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()
    
    @validator('top_k')
    def validate_top_k(cls, v):
        if v > constants.MAX_SEARCH_TOP_K:
            raise ValueError(f"top_k cannot exceed {constants.MAX_SEARCH_TOP_K}")
        if v < 1:
            raise ValueError("top_k must be at least 1")
        return v

@router.post("/hybrid-search")
@limiter.limit("60/minute")
async def hybrid_search_endpoint(request: Request, search_request: HybridSearchRequest):
    """Enhanced search with validation and error handling"""
    try:
        logger.db_query("hybrid search", f"query: '{search_request.query[:50]}'", search_request.top_k)
        
        results = search_engine.search_with_custom_weights(
            query=search_request.query,
            top_k=search_request.top_k,
            dense_weight=search_request.dense_weight,
            sparse_weight=search_request.sparse_weight
        )
        
        if not results:
            logger.info(f"No results found for: '{search_request.query[:50]}'")
            return {
                "message": "No results found",
                "query": search_request.query,
                "results": []
            }
        
        logger.db_query("hybrid search", f"query: '{search_request.query[:50]}'", len(results))
        return {
            "query": search_request.query,
            "total_results": len(results),
            "results": results
        }
        
    except ValidationError:
        raise
    except Exception as e:
        logger.db_error("hybrid search", str(e))
        raise ProcessingError(
            detail="Search operation failed",
            step="hybrid_search",
            query=search_request.query[:50],
            error=str(e)[:200]
        )

class SimpleSearchRequest(BaseModel):
    query: str
    top_k: int = constants.DEFAULT_SEARCH_TOP_K
    
    @validator('top_k')
    def validate_top_k(cls, v):
        if v > constants.MAX_SEARCH_TOP_K:
            raise ValueError(f"top_k cannot exceed {constants.MAX_SEARCH_TOP_K}")
        if v < 1:
            raise ValueError("top_k must be at least 1")
        return v

@router.post("/hybrid-search/balanced")
async def balanced_search(request: SimpleSearchRequest):
    try:
        results = search_engine.search_balanced(request.query, top_k=request.top_k)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
async def analysis_search(request: AnalysisSearchRequest):
    try:
        results = analysis_searcher.search(
            query=request.query,
            top_k=request.top_k
        )
        
        if not results:
            return {
                "message": "No analysis results found",
                "query": request.query,
                "results": []
            }
        
        return {
            "query": request.query,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis search failed: {str(e)}")