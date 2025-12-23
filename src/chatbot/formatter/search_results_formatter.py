"""
Markdown formatter for search results - converts search results to clean markdown
and filters to only include the most relevant/specific parts for LLM consumption.
"""
from typing import List, Dict, Any, Optional
import json


def format_search_results_to_markdown(
    results: List[Dict[str, Any]],
    query: Optional[str] = None,
    include_fields: Optional[List[str]] = None,
    max_summary_length: int = 150,
    max_executive_summary_length: int = 200
) -> str:
    """
    Format search results to clean markdown format.
    Only includes the most relevant/specific parts.
    
    Args:
        results: List of search result dictionaries
        query: Original search query (for context)
        include_fields: Specific fields to include (if None, uses smart defaults)
        max_summary_length: Max characters for summary field
        max_executive_summary_length: Max characters for executive_summary field
    
    Returns:
        Markdown formatted string
    """
    if not results:
        return "## No Results Found\n\nNo search results available."
    
    # Default fields to include (most relevant/specific)
    if include_fields is None:
        include_fields = [
            "product",
            "location", 
            "crop",
            "improvement_percent",
            "executive_summary",  # Most important - already synthesized
            "performance_significance"
        ]
    
    markdown_lines = []
    
    # Header
    if query:
        markdown_lines.append(f"## Search Results: {query}\n")
    else:
        markdown_lines.append("## Search Results\n")
    
    markdown_lines.append(f"**Total Results:** {len(results)}\n")
    
    # Format each result
    for idx, result in enumerate(results, 1):
        markdown_lines.append(f"\n### Result {idx}\n")
        
        # Only include specified fields
        for field in include_fields:
            value = result.get(field)
            
            if value is None or value == "" or value == "N/A":
                continue
            
            # Format based on field type
            if field == "improvement_percent":
                markdown_lines.append(f"- **Improvement:** {value:.1f}%")
            elif field == "executive_summary":
                # Truncate if too long
                summary = str(value)
                if len(summary) > max_executive_summary_length:
                    summary = summary[:max_executive_summary_length] + "..."
                markdown_lines.append(f"- **Summary:** {summary}")
            elif field == "summary":
                # Truncate if too long
                summary = str(value)
                if len(summary) > max_summary_length:
                    summary = summary[:max_summary_length] + "..."
                markdown_lines.append(f"- **Summary:** {summary}")
            elif field == "performance_significance":
                markdown_lines.append(f"- **Significance:** {value}")
            else:
                # Generic field formatting
                markdown_lines.append(f"- **{field.replace('_', ' ').title()}:** {value}")
        
        # Add relevance score if available (for debugging)
        if "score" in result and result.get("score", 0) > 0:
            markdown_lines.append(f"- **Relevance Score:** {result['score']:.3f}")
    
    return "\n".join(markdown_lines)


def format_single_result_to_markdown(
    result: Dict[str, Any],
    focus_fields: Optional[List[str]] = None
) -> str:
    """
    Format a single search result to markdown.
    Focuses on the most specific/relevant parts.
    
    Args:
        result: Single search result dictionary
        focus_fields: Fields to focus on (if None, uses smart defaults)
    
    Returns:
        Markdown formatted string
    """
    if not result:
        return "No result data available."
    
    # Smart defaults - only the most relevant fields
    if focus_fields is None:
        focus_fields = [
            "product",
            "location",
            "crop", 
            "improvement_percent",
            "executive_summary"
        ]
    
    markdown_lines = []
    
    # Title
    product = result.get("product", "Unknown Product")
    location = result.get("location", "")
    markdown_lines.append(f"## {product}")
    if location:
        markdown_lines.append(f"**Location:** {location}\n")
    
    # Key metrics first
    improvement = result.get("improvement_percent")
    if improvement is not None:
        markdown_lines.append(f"**Improvement:** {improvement:.1f}%")
    
    significance = result.get("performance_significance")
    if significance:
        markdown_lines.append(f"**Performance Significance:** {significance}")
    
    # Executive summary (most important)
    exec_summary = result.get("executive_summary")
    if exec_summary:
        markdown_lines.append(f"\n### Summary\n{exec_summary[:300]}")
    
    # Other focused fields
    for field in focus_fields:
        if field in ["product", "location", "improvement_percent", "executive_summary"]:
            continue  # Already handled
        
        value = result.get(field)
        if value and value != "N/A":
            markdown_lines.append(f"\n**{field.replace('_', ' ').title()}:** {value}")
    
    return "\n".join(markdown_lines)


def extract_most_relevant_parts(
    result: Dict[str, Any],
    query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract only the most relevant/specific parts from a result.
    Filters out unnecessary data.
    
    Args:
        result: Full search result dictionary
        query: Original query to determine relevance
    
    Returns:
        Filtered dictionary with only relevant fields
    """
    # Core fields (always include)
    relevant = {
        "product": result.get("product"),
        "location": result.get("location"),
        "crop": result.get("crop"),
        "improvement_percent": result.get("improvement_percent"),
    }
    
    # Most important: executive_summary (already synthesized)
    if result.get("executive_summary"):
        relevant["executive_summary"] = result.get("executive_summary")[:300]  # Limit length
    
    # Performance metrics
    if result.get("performance_significance"):
        relevant["performance_significance"] = result.get("performance_significance")
    
    # Only include if query is about these
    if query:
        query_lower = query.lower()
        
        # If query mentions cooperator, include cooperator feedback
        if "cooperator" in query_lower or "feedback" in query_lower:
            if result.get("cooperator_feedback"):
                relevant["cooperator_feedback"] = result.get("cooperator_feedback")[:200]
        
        # If query mentions season, include season
        if "season" in query_lower or "wet" in query_lower or "dry" in query_lower:
            if result.get("season"):
                relevant["season"] = result.get("season")
    
    # Remove None/empty values
    return {k: v for k, v in relevant.items() if v is not None and v != "" and v != "N/A"}


def format_results_for_summary_tool(
    results: List[Dict[str, Any]],
    query: Optional[str] = None
) -> str:
    """
    Format results specifically for the generate_summary_tool.
    Only includes the most essential parts for synthesis.
    
    Args:
        results: List of search results
        query: Original query
    
    Returns:
        Markdown formatted string optimized for summary generation
    """
    if not results:
        return "No results to summarize."
    
    markdown_lines = []
    markdown_lines.append(f"## Results to Summarize ({len(results)} reports)\n")
    
    for idx, result in enumerate(results, 1):
        # Extract only most relevant parts
        relevant = extract_most_relevant_parts(result, query)
        
        markdown_lines.append(f"\n### Report {idx}: {relevant.get('product', 'Unknown')}")
        
        if relevant.get("location"):
            markdown_lines.append(f"**Location:** {relevant['location']}")
        
        if relevant.get("improvement_percent") is not None:
            markdown_lines.append(f"**Improvement:** {relevant['improvement_percent']:.1f}%")
        
        # Executive summary is the key part for synthesis
        if relevant.get("executive_summary"):
            markdown_lines.append(f"\n**Summary:**\n{relevant['executive_summary']}")
    
    return "\n".join(markdown_lines)

