"""
Workflow operation scores for Langfuse dashboard

This module handles all score tracking for workflow processing operations.
"""

from typing import Dict, Any
from src.core.config import LANGFUSE_CONFIGURED
from src.shared.score_helper import score_current_trace
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def log_workflow_scores(final_state: Dict[str, Any]) -> None:
    """
    Log all workflow-related scores to Langfuse trace
    
    Args:
        final_state: Final processing state containing analysis results and evaluation data
    """
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        # Calculate scores for dashboard
        workflow_success = len(final_state.get("errors", [])) == 0
        error_count = len(final_state.get("errors", []))
        
        # Get evaluation confidence if available
        evaluation = final_state.get("output_evaluation", {})
        if isinstance(evaluation, list) and evaluation:
            evaluation = evaluation[0]
        evaluation_confidence = (
            evaluation.get("confidence", 0.5) 
            if isinstance(evaluation, dict) else 0.5
        )
        
        # Get data quality score if available
        analysis = final_state.get("analysis_result", {})
        data_quality_score = (
            analysis.get("data_quality", {}).get("completeness_score", 0) 
            if analysis else 0
        )
        
        # Log all scores
        score_current_trace(
            name="workflow_success",
            value=1.0 if workflow_success else 0.0,
            data_type="BOOLEAN",
            comment=(
                "Workflow completed successfully" 
                if workflow_success 
                else f"Workflow completed with {error_count} error(s)"
            )
        )
        
        score_current_trace(
            name="evaluation_confidence",
            value=evaluation_confidence,
            data_type="NUMERIC",
            comment="Quality evaluation confidence score (0-1)"
        )
        
        if data_quality_score > 0:
            score_current_trace(
                name="data_quality",
                value=data_quality_score / 100.0,  # Convert to 0-1 scale
                data_type="NUMERIC",
                comment="Data completeness and quality score (0-1)"
            )
        
    except Exception as e:
        logger.debug(f"Could not add workflow scores to trace: {e}")

