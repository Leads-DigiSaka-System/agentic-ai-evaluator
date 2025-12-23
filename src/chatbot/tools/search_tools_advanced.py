"""
Advanced search tools for chat agent - specialized search capabilities
"""
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from src.database.analysis_search import analysis_searcher
from src.utils.clean_logger import get_clean_logger
from src.chatbot.formatter.search_results_formatter import (
    format_search_results_to_markdown,
    extract_most_relevant_parts
)
import json
import asyncio

logger = get_clean_logger(__name__)


@tool
def search_by_form_type_tool(
    form_type: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by form type.
    
    Use this tool when the user asks about specific form types:
    - "Show me foliar demo forms"
    - "Find herbicide demo reports"
    
    Args:
        form_type: Form type (e.g., "Foliar/Biostimulant Demo Form", "Herbicide Demo Form")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with form-type-specific analysis results
    """
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    
    query = f"form type: {form_type}"
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_date_range_tool(
    start_date: str = None,
    end_date: str = None,
    date_field: str = "application_date",
    top_k: int = 10,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by date range.
    
    Use this tool when the user asks:
    - "Show me demos from January 2024"
    - "Find reports between dates"
    - "What demos were done in 2024?"
    
    Args:
        start_date: Start date (YYYY-MM-DD format, optional)
        end_date: End date (YYYY-MM-DD format, optional)
        date_field: Which date field to search - "application_date", "planting_date", or "insertion_date" (default: "application_date")
        top_k: Number of results to return (default: 10)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with date-filtered analysis results
    """
    if not cooperative:
        return '{"error": "Cooperative ID is required", "results": []}'
    
    # Build query
    if start_date and end_date:
        query = f"{date_field} between {start_date} and {end_date}"
    elif start_date:
        query = f"{date_field} from {start_date}"
    elif end_date:
        query = f"{date_field} before {end_date}"
    else:
        query = f"all reports by {date_field}"
    
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_metric_type_tool(
    metric_type: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by metric type.
    
    Use this tool when the user asks about specific measurement types:
    - "Show me rating scale demos"
    - "Find percentage-based results"
    - "What count data demos do we have?"
    
    Args:
        metric_type: Metric type - "rating_scale", "percentage", "count", or "measurement"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with metric-type-specific analysis results
    """
    metric_lower = metric_type.lower().strip().replace(" ", "_")
    valid_types = ["rating_scale", "percentage", "count", "measurement"]
    
    if metric_lower not in valid_types:
        return f'{{"error": "Metric type must be one of: {valid_types}", "results": []}}'
    
    query = f"metric type: {metric_lower}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_confidence_level_tool(
    confidence_level: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by confidence level.
    
    Use this tool when the user asks:
    - "Show me high confidence results"
    - "Find reports with medium confidence"
    - "What low confidence demos do we have?"
    
    Args:
        confidence_level: Confidence level - "high", "medium", or "low"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with confidence-level-filtered analysis results
    """
    confidence_lower = confidence_level.lower().strip()
    valid_levels = ["high", "medium", "low"]
    
    if confidence_lower not in valid_levels:
        return f'{{"error": "Confidence level must be one of: {valid_levels}", "results": []}}'
    
    query = f"confidence level {confidence_lower}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_data_quality_tool(
    min_quality: float = 0.0,
    max_quality: float = 100.0,
    top_k: int = 10,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by data quality score.
    
    Use this tool when the user asks:
    - "Show me high quality data reports"
    - "Find reports with quality score >80"
    - "What low quality demos do we have?"
    
    Args:
        min_quality: Minimum data quality score (0-100, default: 0.0)
        max_quality: Maximum data quality score (0-100, default: 100.0)
        top_k: Number of results to return (default: 10)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with quality-filtered analysis results
    """
    if not cooperative:
        return '{"error": "Cooperative ID is required", "results": []}'
    
    # Build query
    if min_quality > 0 and max_quality < 100:
        query = f"data quality between {min_quality} and {max_quality} high quality"
    elif min_quality > 0:
        query = f"data quality greater than {min_quality} high quality"
    elif max_quality < 100:
        query = f"data quality less than {max_quality} low quality"
    else:
        query = "all reports"
    
    # Use general search and filter results
    try:
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
        
        # Filter by quality range
        filtered_results = []
        for result in results:
            quality = result.get("data_quality_score", 0.0)
            if min_quality <= quality <= max_quality:
                filtered_results.append(result)
            if len(filtered_results) >= top_k:
                break
        
        if not filtered_results:
            filter_msg = f"data quality between {min_quality} and {max_quality}"
            return f"## No Results Found\n\nNo results found with {filter_msg}"
        
        # Extract only most relevant parts to save tokens
        relevant_results = []
        for result in filtered_results:
            relevant = extract_most_relevant_parts(result, query)
            relevant_results.append(relevant)
        
        # Format as markdown
        query_with_filter = f"{query} (filter: {min_quality}-{max_quality} quality score)"
        return format_search_results_to_markdown(
            results=relevant_results,
            query=query_with_filter,
            max_summary_length=150,
            max_executive_summary_length=200
        )
        
    except Exception as e:
        logger.error(f"Search by data quality error: {str(e)}", exc_info=True)
        return f'{{"error": "Search failed: {str(e)}", "results": []}}'


@tool
def search_by_control_product_tool(
    control_product_name: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by control product name.
    
    Use this tool when the user asks about demos comparing against a specific control product.
    
    Args:
        control_product_name: Name of the control product (e.g., "FP", "Untreated", "Control")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with control-product-specific analysis results
    """
    query = f"control product: {control_product_name}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_speed_of_action_tool(
    speed: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by speed of action.
    
    Use this tool when the user asks:
    - "Show me fast-acting products"
    - "Find demos with slow action"
    - "What products have moderate speed?"
    
    Args:
        speed: Speed of action - "fast", "moderate", or "slow"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with speed-filtered analysis results
    """
    speed_lower = speed.lower().strip()
    valid_speeds = ["fast", "moderate", "slow"]
    
    if speed_lower not in valid_speeds:
        return f'{{"error": "Speed must be one of: {valid_speeds}", "results": []}}'
    
    query = f"speed of action {speed_lower}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_yield_status_tool(
    yield_status: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by yield data status.
    
    Use this tool when the user asks:
    - "Show me demos with available yield data"
    - "Find reports with pending yield"
    - "What demos don't have yield measurements?"
    
    Args:
        yield_status: Yield status - "available", "pending", or "not_measured"
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with yield-status-filtered analysis results
    """
    status_lower = yield_status.lower().strip().replace(" ", "_")
    valid_statuses = ["available", "pending", "not_measured"]
    
    if status_lower not in valid_statuses:
        return f'{{"error": "Yield status must be one of: {valid_statuses}", "results": []}}'
    
    query = f"yield status {status_lower}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_yield_improvement_range_tool(
    min_yield_improvement: float = 0.0,
    max_yield_improvement: float = 100.0,
    top_k: int = 10,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by yield improvement percentage range.
    
    Use this tool when the user asks:
    - "Show me products with >20% yield improvement"
    - "Find demos with high yield gains"
    - "What products have low yield improvement?"
    
    Args:
        min_yield_improvement: Minimum yield improvement percentage (default: 0.0)
        max_yield_improvement: Maximum yield improvement percentage (default: 100.0)
        top_k: Number of results to return (default: 10)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with yield-improvement-filtered results
    """
    if not cooperative:
        return '{"error": "Cooperative ID is required", "results": []}'
    
    # Build query
    if min_yield_improvement > 0 and max_yield_improvement < 100:
        query = f"yield improvement between {min_yield_improvement}% and {max_yield_improvement}%"
    elif min_yield_improvement > 0:
        query = f"yield improvement greater than {min_yield_improvement}% high yield gain"
    elif max_yield_improvement < 100:
        query = f"yield improvement less than {max_yield_improvement}% low yield gain"
    else:
        query = "all reports with yield data"
    
    # Use general search and filter results
    try:
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
        
        # Filter by yield improvement range
        filtered_results = []
        for result in results:
            # Try to get yield_improvement_percent from result
            yield_improvement = result.get("yield_improvement_percent", 0.0)
            if isinstance(yield_improvement, (int, float)) and min_yield_improvement <= yield_improvement <= max_yield_improvement:
                filtered_results.append(result)
            if len(filtered_results) >= top_k:
                break
        
        if not filtered_results:
            filter_msg = f"yield improvement between {min_yield_improvement}% and {max_yield_improvement}%"
            return f"## No Results Found\n\nNo results found with {filter_msg}"
        
        # Extract only most relevant parts to save tokens
        relevant_results = []
        for result in filtered_results:
            relevant = extract_most_relevant_parts(result, query)
            relevant_results.append(relevant)
        
        # Format as markdown
        query_with_filter = f"{query} (filter: {min_yield_improvement}%-{max_yield_improvement}% yield improvement)"
        return format_search_results_to_markdown(
            results=relevant_results,
            query=query_with_filter,
            max_summary_length=150,
            max_executive_summary_length=200
        )
        
    except Exception as e:
        logger.error(f"Search by yield improvement range error: {str(e)}", exc_info=True)
        return f'{{"error": "Search failed: {str(e)}", "results": []}}'


@tool
def search_by_measurement_intervals_tool(
    interval: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by measurement interval.
    
    Use this tool when the user asks about demos measured at specific intervals:
    - "Show me demos measured at 3 DAA"
    - "Find reports with 7 DAA measurements"
    - "What demos have 14 DAA data?"
    
    Args:
        interval: Measurement interval (e.g., "3 DAA", "7 DAA", "14 DAA", "10 DAA")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with interval-specific analysis results
    """
    query = f"measurement interval {interval}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_metrics_detected_tool(
    metric_name: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by detected metric.
    
    Use this tool when the user asks about specific metrics:
    - "Show me demos with tiller measurements"
    - "Find reports with LCC data"
    - "What demos measured yield?"
    
    Args:
        metric_name: Name of the metric (e.g., "tillers", "LCC", "yield", "% control")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with metric-specific analysis results
    """
    query = f"metric detected: {metric_name}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_risk_factors_tool(
    risk_keyword: str = None,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by risk factors.
    
    Use this tool when the user asks:
    - "Show me demos with risk factors"
    - "Find reports with high risk"
    - "What demos have small plot size risks?"
    
    Args:
        risk_keyword: Optional keyword to search within risk factors (e.g., "small plot", "missing data")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with risk-factor-filtered analysis results
    """
    if risk_keyword:
        query = f"risk factors {risk_keyword}"
    else:
        query = "reports with risk factors"
    
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_opportunities_tool(
    opportunity_keyword: str = None,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by opportunities.
    
    Use this tool when the user asks:
    - "Show me demos with opportunities"
    - "Find reports with high potential"
    - "What demos have strong performance opportunities?"
    
    Args:
        opportunity_keyword: Optional keyword to search within opportunities (e.g., "strong performance", "quick results")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with opportunity-filtered analysis results
    """
    if opportunity_keyword:
        query = f"opportunities {opportunity_keyword}"
    else:
        query = "reports with opportunities"
    
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_recommendations_tool(
    recommendation_keyword: str = None,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by recommendations.
    
    Use this tool when the user asks:
    - "Show me demos with recommendations"
    - "Find reports with high priority recommendations"
    - "What demos recommend follow-up trials?"
    
    Args:
        recommendation_keyword: Optional keyword to search within recommendations (e.g., "follow-up", "expand", "replicate")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with recommendation-filtered analysis results
    """
    if recommendation_keyword:
        query = f"recommendations {recommendation_keyword}"
    else:
        query = "reports with recommendations"
    
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_key_observation_tool(
    observation_keyword: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by key observation.
    
    Use this tool when the user asks about specific observations:
    - "Show me demos with early performance observations"
    - "Find reports mentioning visible results"
    
    Args:
        observation_keyword: Keyword to search in key observations
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with observation-filtered analysis results
    """
    query = f"key observation {observation_keyword}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })


@tool
def search_by_scale_info_tool(
    scale_keyword: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Search for analysis reports by rating scale information.
    
    Use this tool when the user asks about specific rating scales:
    - "Show me demos using 1-4 scale"
    - "Find reports with Excellent rating scale"
    
    Args:
        scale_keyword: Keyword to search in scale info (e.g., "1-4", "Excellent", "rating")
        top_k: Number of results to return (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with scale-info-filtered analysis results
    """
    query = f"rating scale {scale_keyword}"
    # Import here to avoid circular import
    from src.chatbot.tools.search_tools import search_analysis_tool
    return search_analysis_tool.invoke({
        "query": query,
        "top_k": top_k,
        "cooperative": cooperative
    })

