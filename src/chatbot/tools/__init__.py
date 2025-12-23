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
    search_by_performance_significance_tool,
    search_by_applicant_tool
)
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
    # Basic search tools (11)
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
    "search_by_applicant_tool",
    # Advanced search tools (16)
    "search_by_form_type_tool",
    "search_by_date_range_tool",
    "search_by_metric_type_tool",
    "search_by_confidence_level_tool",
    "search_by_data_quality_tool",
    "search_by_control_product_tool",
    "search_by_speed_of_action_tool",
    "search_by_yield_status_tool",
    "search_by_yield_improvement_range_tool",
    "search_by_measurement_intervals_tool",
    "search_by_metrics_detected_tool",
    "search_by_risk_factors_tool",
    "search_by_opportunities_tool",
    "search_by_recommendations_tool",
    "search_by_key_observation_tool",
    "search_by_scale_info_tool",
    # List tools (3)
    "list_reports_tool",
    "get_stats_tool",
    "get_report_by_id_tool",
    # Analysis tools (3)
    "compare_products_tool",
    "generate_summary_tool",
    "get_trends_tool",
]

