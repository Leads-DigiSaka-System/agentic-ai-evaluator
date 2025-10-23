from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.database.hybrid_search import LangChainHybridSearch
from src.database.analysis_search import analysis_searcher 

router = APIRouter()
search_engine = LangChainHybridSearch()

class HybridSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    dense_weight: float = 0.7
    sparse_weight: float = 0.3

@router.post("/hybrid-search")
async def hybrid_search_endpoint(request: HybridSearchRequest):
    try:
        # Use the correct method that accepts custom weights
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
    top_k: int = 5

@router.post("/hybrid-search/balanced")
async def balanced_search(request: SimpleSearchRequest):
    try:
        results = search_engine.search_balanced(request.query, top_k=request.top_k)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AnalysisSearchRequest(BaseModel):
    query: str
    top_k: int = 5

@router.post("/analysis-search")
async def analysis_search(request: AnalysisSearchRequest):
    """
    Search through agricultural analysis data using semantic search.
    
    Args:
        query: Search query (e.g., "corn yield improvement", "rice fertilizer demo")
        top_k: Number of results to return (default: 5)
    
    Returns:
        List of analysis results with performance metrics and summaries
    """
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