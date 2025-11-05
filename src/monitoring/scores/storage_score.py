"""
Storage operation scores for Langfuse dashboard

This module handles all score tracking for storage approval operations.
"""

from typing import List, Dict, Any
from src.utils.config import LANGFUSE_CONFIGURED
from src.monitoring.trace.langfuse_helper import score_current_trace
from src.utils.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def log_storage_rejection_scores() -> None:
    """
    Log scores for storage rejection by user
    
    This is called when user rejects storage approval.
    """
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        score_current_trace(
            name="user_approval",
            value=0.0,
            data_type="BOOLEAN",
            comment="User rejected storage"
        )
    except Exception as e:
        logger.debug(f"Could not add rejection scores to trace: {e}")


def log_storage_scores(
    reports: List[Dict[str, Any]],
    cached_output: Dict[str, Any],
    result: Dict[str, Any],
    storage_type: str
) -> None:
    """
    Log all storage-related scores to Langfuse trace
    
    Args:
        reports: List of reports being stored
        cached_output: Cached agent output containing evaluation data
        result: Storage operation result
        storage_type: "single" or "batch"
    """
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        storage_status = result.get("status", "unknown")
        storage_success = storage_status in ["success", "completed"]
        
        # Get metrics from first report for scoring
        first_report = reports[0] if reports else {}
        analysis = first_report.get("analysis", {})
        data_quality_score = (
            analysis.get("data_quality", {}).get("completeness_score", 0) 
            if analysis else 0
        )
        
        # Get evaluation confidence if available
        # Check both cached_output level and individual reports
        evaluation_confidence = 0.5  # Default
        
        # Check in cached output first (top-level)
        if "output_evaluation" in cached_output:
            eval_data = cached_output.get("output_evaluation", {})
            if isinstance(eval_data, dict):
                evaluation_confidence = eval_data.get("confidence", 0.5)
            elif isinstance(eval_data, list) and eval_data:
                eval_data = eval_data[0]
                if isinstance(eval_data, dict):
                    evaluation_confidence = eval_data.get("confidence", 0.5)
        
        # Also check in first report (might be stored per report)
        if evaluation_confidence == 0.5 and "output_evaluation" in first_report:
            eval_data = first_report.get("output_evaluation", {})
            if isinstance(eval_data, dict):
                evaluation_confidence = eval_data.get("confidence", 0.5)
            elif isinstance(eval_data, list) and eval_data:
                eval_data = eval_data[0]
                if isinstance(eval_data, dict):
                    evaluation_confidence = eval_data.get("confidence", 0.5)
        
        # Get analysis quality metrics
        performance_analysis = analysis.get("performance_analysis", {})
        statistical_assessment = performance_analysis.get("statistical_assessment", {})
        confidence_level = statistical_assessment.get("confidence_level", "medium")
        improvement_significance = statistical_assessment.get("improvement_significance", "moderate")
        
        # Map confidence level to numeric (high=1.0, medium=0.7, low=0.4)
        confidence_score_map = {"high": 1.0, "medium": 0.7, "low": 0.4}
        analysis_confidence_score = confidence_score_map.get(confidence_level.lower(), 0.7)
        
        # Map significance to numeric (highly_significant=1.0, significant=0.8, moderate=0.6, marginal=0.4)
        significance_score_map = {
            "highly_significant": 1.0,
            "significant": 0.8,
            "moderate": 0.6,
            "marginal": 0.4
        }
        significance_score = significance_score_map.get(improvement_significance.lower(), 0.6)
        
        # Get chart count for quality assessment
        graph_suggestions = first_report.get("graph_suggestions", {})
        chart_count = len(graph_suggestions.get("suggested_charts", []))
        chart_quality_score = min(1.0, chart_count / 3.0)  # Normalize: 3+ charts = 1.0
        
        # Calculate overall readiness score (composite)
        readiness_factors = []
        if data_quality_score > 0:
            readiness_factors.append(data_quality_score / 100.0)
        readiness_factors.append(evaluation_confidence)
        readiness_factors.append(analysis_confidence_score)
        overall_readiness = (
            sum(readiness_factors) / len(readiness_factors) 
            if readiness_factors else 0.5
        )
        
        # Calculate batch success rate if batch storage
        batch_success_rate = 1.0
        if storage_type == "batch" and "successful_items" in result:
            total_items = result.get("total_items", len(reports))
            successful_items = result.get("successful_items", 0)
            if total_items > 0:
                batch_success_rate = successful_items / total_items
        
        # Log all scores
        score_current_trace(
            name="user_approval",
            value=1.0,
            data_type="BOOLEAN",
            comment="User approved storage"
        )
        
        score_current_trace(
            name="storage_success",
            value=1.0 if storage_success else 0.0,
            data_type="BOOLEAN",
            comment=f"Storage operation {'succeeded' if storage_success else 'failed'}"
        )
        
        if data_quality_score > 0:
            score_current_trace(
                name="data_quality",
                value=data_quality_score / 100.0,  # Convert to 0-1 scale
                data_type="NUMERIC",
                comment="Data completeness score from analysis (0-1)"
            )
        
        score_current_trace(
            name="evaluation_confidence",
            value=evaluation_confidence,
            data_type="NUMERIC",
            comment="Quality evaluation confidence from evaluator agent (0-1)"
        )
        
        score_current_trace(
            name="analysis_confidence",
            value=analysis_confidence_score,
            data_type="NUMERIC",
            comment=f"Analysis confidence level: {confidence_level}"
        )
        
        score_current_trace(
            name="improvement_significance",
            value=significance_score,
            data_type="NUMERIC",
            comment=f"Performance improvement significance: {improvement_significance}"
        )
        
        if chart_count > 0:
            score_current_trace(
                name="chart_quality",
                value=chart_quality_score,
                data_type="NUMERIC",
                comment=f"Chart quality based on count: {chart_count} charts"
            )
        
        score_current_trace(
            name="overall_readiness",
            value=overall_readiness,
            data_type="NUMERIC",
            comment="Overall storage readiness score (composite of data quality, evaluation, and analysis confidence)"
        )
        
        if storage_type == "batch":
            score_current_trace(
                name="batch_success_rate",
                value=batch_success_rate,
                data_type="NUMERIC",
                comment=f"Batch storage success rate: {result.get('successful_items', 0)}/{result.get('total_items', len(reports))}"
            )
        
    except Exception as e:
        logger.debug(f"Could not add storage scores to trace: {e}")

