
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from src.database.analysis_search import analysis_searcher
from src.utils.clean_logger import get_clean_logger
import json

logger = get_clean_logger(__name__)


@tool
def search_analysis_tool(
    query: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for agricultural analysis reports using natural language query.
    
    Use this tool when the user asks about:
    - Products, crops, locations, or demo results
    - Performance data, improvement percentages
    - Analysis reports or findings
    
    Args:
        query: Natural language search query (e.g., "rice fertilizer demos", "best performing products")
        top_k: Number of results to return (default: 5, max: 100)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with search results including product names, locations, improvement percentages, and summaries
    
    Example queries:
        - "Show me rice fertilizer demos"
        - "What products have high improvement?"
        - "Find corn demos in Laguna"
    """
    try:
        if not query or not query.strip():
            return '{"error": "Query cannot be empty", "results": []}'
        
        if top_k < 1:
            top_k = 5
        if top_k > 100:
            top_k = 100
        
        if not cooperative:
            return '{"error": "Cooperative ID is required", "results": []}'
        
        # Call the existing search function (async)
        # Note: LangChain tools are sync, but our search is async
        # We need to handle this properly
        import asyncio
        
        # Try to get existing event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async search
        if loop.is_running():
            # If loop is already running, we need to use a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    analysis_searcher.search(query, top_k=top_k, cooperative=cooperative)
                )
                results = future.result(timeout=30)
        else:
            # Run in existing loop
            results = loop.run_until_complete(
                analysis_searcher.search(query, top_k=top_k, cooperative=cooperative)
            )
        
        if not results:
            return f'{{"message": "No results found for query: {query}", "results": [], "query": "{query}"}}'
        
        # Format results for LLM consumption
        formatted_results = []
        for result in results:
            formatted_result = {
                "product": result.get("product", "N/A"),
                "location": result.get("location", "N/A"),
                "crop": result.get("crop", "N/A"),
                "improvement_percent": result.get("improvement_percent", 0.0),
                "summary": result.get("summary", "")[:200],  # Limit summary length
                "executive_summary": result.get("executive_summary", "")[:300],
                "score": result.get("score", 0.0)
            }
            formatted_results.append(formatted_result)
        
        import json
        return json.dumps({
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Search tool error: {str(e)}", exc_info=True)
        return f'{{"error": "Search failed: {str(e)}", "results": []}}'


@tool
def search_by_product_tool(
    product_name: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by specific product name.
    
    Use this tool when the user asks about a specific product.
    
    Args:
        product_name: Name of the product to search for
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with product-specific analysis results
    """
    query = f"product: {product_name}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_location_tool(
    location: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by location.
    
    Use this tool when the user asks about demos or results in a specific location.
    
    Args:
        location: Location name (e.g., "Laguna", "Nueva Ecija")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with location-specific analysis results
    """
    query = f"location: {location}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_crop_tool(
    crop_type: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by crop type.
    
    Use this tool when the user asks about specific crops (e.g., rice, corn, vegetables).
    
    Args:
        crop_type: Type of crop (e.g., "rice", "corn", "vegetables")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with crop-specific analysis results
    """
    query = f"crop: {crop_type}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_cooperator_tool(
    cooperator_name: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by cooperator name.
    
    Use this tool when the user asks about demos or results from a specific cooperator.
    
    Args:
        cooperator_name: Name of the cooperator to search for
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with cooperator-specific analysis results
    """
    query = f"cooperator: {cooperator_name}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_season_tool(
    season: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by season (wet or dry).
    
    Use this tool when the user asks about demos in a specific season.
    
    Args:
        season: Season type - "wet" or "dry"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with season-specific analysis results
    """
    season_lower = season.lower().strip()
    if season_lower not in ["wet", "dry"]:
        return '{"error": "Season must be either \'wet\' or \'dry\'", "results": []}'
    
    query = f"season: {season_lower}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_improvement_range_tool(
    min_improvement: float = 0.0,
    max_improvement: float = 100.0,
    top_k: int = 10,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by improvement percentage range.
    
    Use this tool when the user asks:
    - "Show me products with >80% improvement"
    - "Find demos with high performance"
    - "What products have low improvement?"
    
    Args:
        min_improvement: Minimum improvement percentage (default: 0.0)
        max_improvement: Maximum improvement percentage (default: 100.0)
        top_k: Number of results to return (default: 10)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with filtered results by improvement range
    """
    if not cooperative:
        return '{"error": "Cooperative ID is required", "results": []}'
    
    # Build query for improvement range
    if min_improvement > 0 and max_improvement < 100:
        query = f"improvement between {min_improvement}% and {max_improvement}%"
    elif min_improvement > 0:
        query = f"improvement greater than {min_improvement}% high performance"
    elif max_improvement < 100:
        query = f"improvement less than {max_improvement}% low performance"
    else:
        query = "all reports"
    
    # Use general search and filter results
    try:
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    analysis_searcher.search(query, top_k=top_k * 2, cooperative=cooperative)  # Get more to filter
                )
                results = future.result(timeout=30)
        else:
            results = loop.run_until_complete(
                analysis_searcher.search(query, top_k=top_k * 2, cooperative=cooperative)
            )
        
        # Filter by improvement range
        filtered_results = []
        for result in results:
            improvement = result.get("improvement_percent", 0.0)
            if min_improvement <= improvement <= max_improvement:
                filtered_results.append(result)
            if len(filtered_results) >= top_k:
                break
        
        if not filtered_results:
            return json.dumps({
                "query": query,
                "filter": {"min_improvement": min_improvement, "max_improvement": max_improvement},
                "message": f"No results found with improvement between {min_improvement}% and {max_improvement}%",
                "results": []
            })
        
        # Format results
        formatted_results = []
        for result in filtered_results:
            formatted_result = {
                "product": result.get("product", "N/A"),
                "location": result.get("location", "N/A"),
                "crop": result.get("crop", "N/A"),
                "improvement_percent": result.get("improvement_percent", 0.0),
                "summary": result.get("summary", "")[:200],
                "executive_summary": result.get("executive_summary", "")[:300],
                "score": result.get("score", 0.0)
            }
            formatted_results.append(formatted_result)
        
        return json.dumps({
            "query": query,
            "filter": {"min_improvement": min_improvement, "max_improvement": max_improvement},
            "total_results": len(formatted_results),
            "results": formatted_results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Search by improvement range error: {str(e)}", exc_info=True)
        return f'{{"error": "Search failed: {str(e)}", "results": []}}'


@tool
def search_by_sentiment_tool(
    sentiment: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by cooperator feedback sentiment.
    
    Use this tool when the user asks:
    - "Show me demos with positive feedback"
    - "Find reports with negative cooperator feedback"
    
    Args:
        sentiment: Sentiment type - "positive", "negative", "neutral", or "mixed"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with sentiment-filtered analysis results
    """
    sentiment_lower = sentiment.lower().strip()
    valid_sentiments = ["positive", "negative", "neutral", "mixed"]
    
    if sentiment_lower not in valid_sentiments:
        return f'{{"error": "Sentiment must be one of: {valid_sentiments}", "results": []}}'
    
    query = f"cooperator feedback {sentiment_lower} sentiment"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_product_category_tool(
    category: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by product category.
    
    Use this tool when the user asks about specific product types:
    - "Show me herbicide demos"
    - "Find foliar fertilizer results"
    - "What fungicide demos do we have?"
    
    Args:
        category: Product category (e.g., "herbicide", "foliar", "fungicide", "insecticide", "molluscicide", "fertilizer")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with category-specific analysis results
    """
    query = f"product category: {category}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_performance_significance_tool(
    significance: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by performance significance level.
    
    Use this tool when the user asks:
    - "Show me highly significant results"
    - "Find demos with significant improvement"
    
    Args:
        significance: Significance level - "highly_significant", "significant", "moderate", or "marginal"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with significance-filtered analysis results
    """
    significance_lower = significance.lower().strip().replace(" ", "_")
    valid_levels = ["highly_significant", "significant", "moderate", "marginal"]
    
    if significance_lower not in valid_levels:
        return f'{{"error": "Significance must be one of: {valid_levels}", "results": []}}'
    
    query = f"performance significance {significance_lower}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


# Helper function to get all search tools with cooperative context
def get_search_tools(cooperative: str) -> List:
    """
    Get all search tools with cooperative context pre-filled.
    
    Args:
        cooperative: Cooperative ID for data isolation
    
    Returns:
        List of LangChain tools with cooperative context
    """
    return [
        search_analysis_tool,
        search_by_product_tool,
        search_by_location_tool,
        search_by_crop_tool,
        search_by_cooperator_tool,
        search_by_season_tool,
        search_by_improvement_range_tool,
        search_by_sentiment_tool,
        search_by_product_category_tool,
        search_by_performance_significance_tool
    ]

