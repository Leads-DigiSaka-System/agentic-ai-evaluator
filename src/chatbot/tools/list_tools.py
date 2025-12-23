"""
List tools for chat agent - wraps existing list reports functionality
"""
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from src.database.list_reports import report_lister
from src.utils.clean_logger import get_clean_logger
from src.chatbot.formatter.search_results_formatter import format_search_results_to_markdown
import json

logger = get_clean_logger(__name__)


@tool
def list_reports_tool(
    limit: int = 10,
    cooperative: str = None
) -> str:
    """
    List all analysis reports for the cooperative.
    
    Use this tool when the user asks:
    - "Show me all reports"
    - "List all demos"
    - "How many reports do we have?"
    - "What reports are available?"
    
    Args:
        limit: Maximum number of reports to return (default: 10, max: 100)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with list of reports including product names, locations, improvement percentages, and dates
    """
    try:
        if limit < 1:
            limit = 10
        if limit > 100:
            limit = 100
        
        if not cooperative:
            return '{"error": "Cooperative ID is required", "reports": []}'
        
        # Call the existing list function (async)
        import asyncio
        
        # Try to get existing event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async list
        if loop.is_running():
            # If loop is already running, we need to use a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    report_lister.list_all_reports(cooperative=cooperative)
                )
                result = future.result(timeout=30)
        else:
            # Run in existing loop
            result = loop.run_until_complete(
                report_lister.list_all_reports(cooperative=cooperative)
            )
        
        if not result or "reports" not in result:
            return "## No Reports Found\n\nNo reports available in the system."
        
        reports = result.get("reports", [])
        total = result.get("total", len(reports))
        
        # Limit results
        limited_reports = reports[:limit]
        
        # Format as markdown (token-efficient)
        # Only include essential fields
        markdown_lines = []
        markdown_lines.append(f"## Reports List\n")
        markdown_lines.append(f"**Total Reports:** {total} | **Showing:** {len(limited_reports)}\n")
        
        for idx, report in enumerate(limited_reports, 1):
            markdown_lines.append(f"\n### Report {idx}")
            markdown_lines.append(f"- **Product:** {report.get('product', 'N/A')}")
            markdown_lines.append(f"- **Location:** {report.get('location', 'N/A')}")
            markdown_lines.append(f"- **Crop:** {report.get('crop', 'N/A')}")
            
            improvement = report.get("improvement_percent")
            if improvement is not None:
                markdown_lines.append(f"- **Improvement:** {improvement:.1f}%")
            
            if report.get("insertion_date"):
                markdown_lines.append(f"- **Date:** {report.get('insertion_date')}")
        
        return "\n".join(markdown_lines)
        
    except Exception as e:
        logger.error(f"List reports tool error: {str(e)}", exc_info=True)
        return f'{{"error": "Failed to list reports: {str(e)}", "reports": []}}'


@tool
def get_stats_tool(
    cooperative: str = None
) -> str:
    """
    Get collection statistics for the cooperative.
    
    Use this tool when the user asks:
    - "How many reports do we have?"
    - "What's our collection stats?"
    - "Show me statistics"
    - "How many demos are in the system?"
    
    Args:
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with statistics including total reports, products, locations, and crops
    """
    try:
        if not cooperative:
            return '{"error": "Cooperative ID is required"}'
        
        # Call the existing stats function (async)
        import asyncio
        
        # Try to get existing event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async stats
        if loop.is_running():
            # If loop is already running, we need to use a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    report_lister.get_collection_stats(cooperative=cooperative)
                )
                stats = future.result(timeout=30)
        else:
            # Run in existing loop
            stats = loop.run_until_complete(
                report_lister.get_collection_stats(cooperative=cooperative)
            )
        
        if not stats:
            return "## Error\n\nFailed to get statistics."
        
        # Format stats as markdown (token-efficient)
        markdown_lines = []
        markdown_lines.append("## Collection Statistics\n")
        markdown_lines.append(f"- **Total Reports:** {stats.get('total_reports', 0)}")
        markdown_lines.append(f"- **Unique Products:** {stats.get('unique_products', 0)}")
        markdown_lines.append(f"- **Unique Locations:** {stats.get('unique_locations', 0)}")
        markdown_lines.append(f"- **Unique Crops:** {stats.get('unique_crops', 0)}")
        
        products = stats.get("products", [])
        if products:
            markdown_lines.append(f"\n### Products ({len(products)}):")
            for product in products[:10]:  # Limit to 10
                markdown_lines.append(f"- {product}")
        
        locations = stats.get("locations", [])
        if locations:
            markdown_lines.append(f"\n### Locations ({len(locations)}):")
            for location in locations[:10]:  # Limit to 10
                markdown_lines.append(f"- {location}")
        
        crops = stats.get("crops", [])
        if crops:
            markdown_lines.append(f"\n### Crops ({len(crops)}):")
            for crop in crops[:10]:  # Limit to 10
                markdown_lines.append(f"- {crop}")
        
        return "\n".join(markdown_lines)
        
    except Exception as e:
        logger.error(f"Get stats tool error: {str(e)}", exc_info=True)
        return f'{{"error": "Failed to get statistics: {str(e)}"}}'


@tool
def get_report_by_id_tool(
    report_id: str,
    cooperative: str = None
) -> str:
    """
    Get a specific report by its ID.
    
    Use this tool when the user asks about a specific report ID.
    
    Args:
        report_id: The form_id or report ID to retrieve
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with the full report details
    """
    try:
        if not report_id or not report_id.strip():
            return '{"error": "Report ID is required"}'
        
        if not cooperative:
            return '{"error": "Cooperative ID is required"}'
        
        # Get all reports and find the one with matching ID
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
                    report_lister.list_all_reports(cooperative=cooperative)
                )
                result = future.result(timeout=30)
        else:
            result = loop.run_until_complete(
                report_lister.list_all_reports(cooperative=cooperative)
            )
        
        if not result or "reports" not in result:
            return '{"error": "No reports found"}'
        
        # Find the report with matching ID
        reports = result.get("reports", [])
        matching_report = None
        
        for report in reports:
            if report.get("id") == report_id or report.get("form_id") == report_id:
                matching_report = report
                break
        
        if not matching_report:
            return f'{{"error": "Report with ID {report_id} not found", "report_id": "{report_id}"}}'
        
        # Return full report details
        return json.dumps({
            "report": matching_report
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Get report by ID tool error: {str(e)}", exc_info=True)
        return f'{{"error": "Failed to get report: {str(e)}"}}'


# Helper function to get all list tools
def get_list_tools(cooperative: str) -> List:
    """
    Get all list tools with cooperative context.
    
    Args:
        cooperative: Cooperative ID for data isolation
    
    Returns:
        List of LangChain tools
    """
    return [
        list_reports_tool,
        get_stats_tool,
        get_report_by_id_tool
    ]

