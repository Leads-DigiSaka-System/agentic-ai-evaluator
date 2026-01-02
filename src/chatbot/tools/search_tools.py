from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from src.database.analysis_search import analysis_searcher
from src.utils.clean_logger import get_clean_logger
from src.chatbot.formatter.search_results_formatter import (
    format_search_results_to_markdown,
    extract_most_relevant_parts
)
import json

logger = get_clean_logger(__name__)


@tool
def search_analysis_tool(
    query: str,
    top_k: int = 5,
    cooperative: str = None,
    applicant: str = None,
    location: str = None
) -> str:
    """
    CRITICAL: Use this tool to search the database for agricultural analysis reports.
    
    YOU MUST USE THIS TOOL when the user asks about:
    - Trials, demos, or reports in any location (e.g., "May trials ba tayo sa Zambales?")
    - Products, crops, locations, or demo results
    - Performance data, improvement percentages
    - Analysis reports or findings
    - Any question about agricultural data
    
    This tool searches the vector database and returns real data. Without calling this tool, you have NO ACCESS to the database.
    
    Args:
        query: Natural language search query (e.g., "trials in Zambales", "rice fertilizer demos", "best performing products")
        top_k: Number of results to return (default: 5, max: 100)
        cooperative: Cooperative ID for data isolation (required, passed automatically - DO NOT include in query)
        applicant: Optional applicant name filter
        location: Optional location name filter
    
    Returns:
        Formatted markdown string with search results including product names, locations, improvement percentages, and summaries
    
    Example queries:
        - "trials in Zambales" → query="trials in Zambales"
        - "Show me rice fertilizer demos" → query="rice fertilizer demos"
        - "What products have high improvement?" → query="products with high improvement"
        - "Find corn demos in Laguna" → query="corn demos in Laguna"
    
    IMPORTANT: Cooperative filtering is automatic - you don't need to include "cooperative" in the query.
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
                    analysis_searcher.search(query, top_k=top_k, cooperative=cooperative, applicant=applicant, location=location)
                )
                results = future.result(timeout=30)
        else:
            # Run in existing loop
            results = loop.run_until_complete(
                analysis_searcher.search(query, top_k=top_k, cooperative=cooperative, applicant=applicant, location=location)
            )
        
        if not results:
            return f"## No Results Found\n\nNo results found for query: {query}"
        
        # Extract only most relevant parts to save tokens
        relevant_results = []
        for result in results:
            relevant = extract_most_relevant_parts(result, query)
            relevant_results.append(relevant)
        
        # Format as markdown (much more token-efficient than JSON)
        return format_search_results_to_markdown(
            results=relevant_results,
            query=query,
            max_summary_length=150,
            max_executive_summary_length=200
        )
        
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
    top_k: int = 10,  # Increased for better matching
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by location.
    
    Use this tool when the user asks about demos in a specific location.
    Handles partial matches (e.g., "Zambales" will match "PI, DIRITA, IBA, ZAMBALES").
    
    Args:
        location: Location name (e.g., "Laguna", "Nueva Ecija", "Zambales")
        top_k: Number of results to return (default: 10, increased for better matching)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with location-specific analysis results
    """
    # Use location name directly for better semantic matching
    # Remove "location:" prefix - just use the location name
    # The search will match locations that contain this name (e.g., "Zambales" in "PI, DIRITA, IBA, ZAMBALES")
    query = location.strip()
    
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative,
        "location": query  # Pass location for post-filtering
    })


@tool
def search_by_crop_tool(
    crop: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by crop type.
    
    Use this tool when the user asks about demos for a specific crop.
    
    Args:
        crop: Crop name (e.g., "Rice", "Corn", "Tomato")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with crop-specific analysis results
    """
    query = f"crop: {crop}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_cooperator_tool(
    cooperator: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by cooperator name.
    
    Use this tool when the user asks about demos from a specific cooperator.
    
    Args:
        cooperator: Cooperator name
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with cooperator-specific analysis results
    """
    query = f"cooperator: {cooperator}"
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
    Search for analysis reports by season.
    
    Use this tool when the user asks about demos from a specific season.
    
    Args:
        season: Season (e.g., "Dry", "Wet", "DS", "WS")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with season-specific analysis results
    """
    query = f"season: {season}"
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
    - "Show me products with >20% improvement"
    - "Find demos with high improvement"
    - "What products have low improvement?"
    
    Args:
        min_improvement: Minimum improvement percentage (default: 0.0)
        max_improvement: Maximum improvement percentage (default: 100.0)
        top_k: Number of results to return (default: 10)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with improvement-range-filtered results
    """
    if not cooperative:
        return '{"error": "Cooperative ID is required", "results": []}'
    
    # Build query
    if min_improvement > 0 and max_improvement < 100:
        query = f"improvement between {min_improvement}% and {max_improvement}%"
    elif min_improvement > 0:
        query = f"improvement greater than {min_improvement}% high improvement"
    elif max_improvement < 100:
        query = f"improvement less than {max_improvement}% low improvement"
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
                    analysis_searcher.search(query, top_k=top_k * 2, cooperative=cooperative)
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
            if isinstance(improvement, (int, float)) and min_improvement <= improvement <= max_improvement:
                filtered_results.append(result)
            if len(filtered_results) >= top_k:
                break
        
        if not filtered_results:
            filter_msg = f"improvement between {min_improvement}% and {max_improvement}%"
            return f"## No Results Found\n\nNo results found with {filter_msg}"
        
        # Extract only most relevant parts to save tokens
        relevant_results = []
        for result in filtered_results:
            relevant = extract_most_relevant_parts(result, query)
            relevant_results.append(relevant)
        
        # Format as markdown
        query_with_filter = f"{query} (filter: {min_improvement}%-{max_improvement}% improvement)"
        return format_search_results_to_markdown(
            results=relevant_results,
            query=query_with_filter,
            max_summary_length=150,
            max_executive_summary_length=200
        )
        
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
    - "Find reports with negative sentiment"
    - "What demos have neutral feedback?"
    
    Args:
        sentiment: Sentiment - "positive", "negative", or "neutral"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with sentiment-filtered analysis results
    """
    sentiment_lower = sentiment.lower().strip()
    valid_sentiments = ["positive", "negative", "neutral"]
    
    if sentiment_lower not in valid_sentiments:
        return f'{{"error": "Sentiment must be one of: {valid_sentiments}", "results": []}}'
    
    query = f"sentiment {sentiment_lower}"
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
    
    Use this tool when the user asks about specific product categories:
    - "Show me fertilizer demos"
    - "Find herbicide reports"
    - "What biostimulant demos do we have?"
    
    Args:
        category: Product category (e.g., "Fertilizer", "Herbicide", "Biostimulant")
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
    Search for analysis reports by performance significance.
    
    Use this tool when the user asks:
    - "Show me statistically significant results"
    - "Find demos with high significance"
    - "What demos have low significance?"
    
    Args:
        significance: Significance level - "high", "medium", or "low"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with significance-filtered analysis results
    """
    significance_lower = significance.lower().strip()
    valid_levels = ["high", "medium", "low"]
    
    if significance_lower not in valid_levels:
        return f'{{"error": "Significance must be one of: {valid_levels}", "results": []}}'
    
    query = f"performance significance {significance_lower}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_applicant_tool(
    applicant_name: str,
    top_k: int = 10,  # Increased to get more results for filtering
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by applicant name.
    
    Use this tool when the user asks about demos or results from a specific applicant.
    Uses exact matching at database level for accurate results.
    
    Args:
        applicant_name: Name of the applicant to search for (e.g., "JOEL AMOS O. MOLINA")
        top_k: Number of results to return (default: 10, increased for better matching)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with applicant-specific analysis results
    """
    # Clean the applicant name - remove extra spaces, normalize
    applicant_clean = " ".join(applicant_name.split())
    
    # Use the name directly for semantic search
    # The applicant filter will be applied at Qdrant level for exact matching
    query = applicant_clean
    
    # Call search_analysis_tool with applicant parameter
    # We need to modify search_analysis_tool to accept applicant parameter
    # For now, use the query with applicant name
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative,
        "applicant": applicant_clean  # Pass applicant for exact matching
    })


# Import advanced search tools from separate file
from src.chatbot.tools.search_tools_advanced import (
    search_by_form_type_tool,
    search_by_date_range_tool,
    search_by_metric_type_tool,
    search_by_confidence_level_tool,
    search_by_data_quality_tool,
    search_by_control_product_tool,
    search_by_speed_of_action_tool,
    search_by_yield_status_tool,
    search_by_yield_improvement_range_tool,
    search_by_measurement_intervals_tool,
    search_by_metrics_detected_tool,
    search_by_risk_factors_tool,
    search_by_opportunities_tool,
    search_by_recommendations_tool,
    search_by_key_observation_tool,
    search_by_scale_info_tool
)


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
        search_by_performance_significance_tool,
        # Newly added search tools
        search_by_applicant_tool,
        search_by_form_type_tool,
        search_by_date_range_tool,
        search_by_metric_type_tool,
        search_by_confidence_level_tool,
        search_by_data_quality_tool,
        search_by_control_product_tool,
        search_by_speed_of_action_tool,
        search_by_yield_status_tool,
        search_by_yield_improvement_range_tool,
        search_by_measurement_intervals_tool,
        search_by_metrics_detected_tool,
        search_by_risk_factors_tool,
        search_by_opportunities_tool,
        search_by_recommendations_tool,
        search_by_key_observation_tool,
        search_by_scale_info_tool
    ]
