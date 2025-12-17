"""
Custom tools for chat agent
"""
from src.chatbot.tools.search_tools import (
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
)
from src.chatbot.tools.list_tools import (
    list_reports_tool,
    get_stats_tool,
    get_report_by_id_tool
)
from src.chatbot.tools.analysis_tools import (
    compare_products_tool,
    generate_summary_tool,
    get_trends_tool
)

__all__ = [
    # Search tools
    "search_analysis_tool",
    "search_by_product_tool",
    "search_by_location_tool",
    "search_by_crop_tool",
    "search_by_cooperator_tool",
    "search_by_season_tool",
    "search_by_improvement_range_tool",
    "search_by_sentiment_tool",
    "search_by_product_category_tool",
    "search_by_performance_significance_tool",
    # List tools
    "list_reports_tool",
    "get_stats_tool",
    "get_report_by_id_tool",
    # Analysis tools
    "compare_products_tool",
    "generate_summary_tool",
    "get_trends_tool",
]

