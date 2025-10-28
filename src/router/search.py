from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator  # ← ADD "validator" here
from src.database.hybrid_search import LangChainHybridSearch
from src.database.analysis_search import analysis_searcher 
from src.utils.limiter_config import limiter 
from src.utils import constants 

router = APIRouter()
search_engine = LangChainHybridSearch()

class HybridSearchRequest(BaseModel):
    query: str
    top_k: int = constants.DEFAULT_SEARCH_TOP_K  # ← Changed from 5
    dense_weight: float = constants.DENSE_WEIGHT_DEFAULT
    sparse_weight: float = constants.SPARSE_WEIGHT_DEFAULT
    
    @validator('top_k')  # ← Now this will work
    def validate_top_k(cls, v):
        if v > constants.MAX_SEARCH_TOP_K:
            raise ValueError(f"top_k cannot exceed {constants.MAX_SEARCH_TOP_K}")
        if v < 1:
            raise ValueError("top_k must be at least 1")
        return v

@router.post("/hybrid-search")
async def hybrid_search_endpoint(request: HybridSearchRequest):
    try:
        results = search_engine.search_with_custom_weights(
            query=request.query,
            top_k=request.top_k,
            dense_weight=request.dense_weight,
            sparse_weight=request.sparse_weight
        )
        if not results:
            return {"message": "No results found"}
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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