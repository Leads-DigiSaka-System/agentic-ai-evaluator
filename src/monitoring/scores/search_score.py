"""
Search operation scores for Langfuse dashboard

This module handles all score tracking for analysis search operations.
"""

from typing import List, Dict, Any
from src.core.config import LANGFUSE_CONFIGURED
from src.shared.score_helper import score_current_trace
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def log_search_scores(results: List[Dict[str, Any]], top_k: int) -> None:
    """
    Log all search-related scores to Langfuse trace
    
    Args:
        results: List of search results
        top_k: Number of results requested
    """
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        # Calculate search quality metrics
        has_results = len(results) > 0
        results_count = len(results)
        
        # Calculate average scores from results
        if has_results:
            # Extract scores and quality metrics
            relevance_scores = [
                r.get("score", 0.0) 
                for r in results 
                if isinstance(r.get("score"), (int, float))
            ]
            data_quality_scores = [
                r.get("data_quality_score", 0.0) 
                for r in results 
                if isinstance(r.get("data_quality_score"), (int, float))
            ]
            improvement_percents = [
                r.get("improvement_percent", 0.0) 
                for r in results 
                if isinstance(r.get("improvement_percent"), (int, float))
            ]
            
            avg_relevance = (
                sum(relevance_scores) / len(relevance_scores) 
                if relevance_scores else 0.0
            )
            avg_data_quality = (
                sum(data_quality_scores) / len(data_quality_scores) 
                if data_quality_scores else 0.0
            )
            avg_improvement = (
                sum(improvement_percents) / len(improvement_percents) 
                if improvement_percents else 0.0
            )
            
            # Get top result quality
            top_result = results[0] if results else {}
            top_relevance = top_result.get("score", 0.0)
            top_data_quality = (
                top_result.get("data_quality_score", 0.0) / 100.0 
                if top_result.get("data_quality_score") else 0.0
            )
            
            # Calculate search efficiency (how well we matched requested vs returned)
            search_efficiency = (
                min(1.0, results_count / top_k) 
                if top_k > 0 else 1.0
            )
            
            # Map performance significance to numeric score
            top_significance = top_result.get("performance_significance", "")
            significance_score_map = {
                "highly_significant": 1.0,
                "significant": 0.8,
                "moderate": 0.6,
                "marginal": 0.4
            }
            top_significance_score = significance_score_map.get(
                top_significance.lower(), 0.6
            )
        else:
            avg_relevance = 0.0
            avg_data_quality = 0.0
            avg_improvement = 0.0
            top_relevance = 0.0
            top_data_quality = 0.0
            search_efficiency = 0.0
            top_significance_score = 0.0
        
        # Log all scores
        score_current_trace(
            name="search_success",
            value=1.0 if has_results else 0.0,
            data_type="BOOLEAN",
            comment="Search returned results" if has_results else "No results found"
        )
        
        if has_results:
            score_current_trace(
                name="search_efficiency",
                value=search_efficiency,
                data_type="NUMERIC",
                comment=f"Search efficiency: {results_count}/{top_k} results returned"
            )
            
            score_current_trace(
                name="avg_relevance_score",
                value=avg_relevance,
                data_type="NUMERIC",
                comment=f"Average relevance score of {results_count} results"
            )
            
            if avg_data_quality > 0:
                score_current_trace(
                    name="avg_data_quality",
                    value=avg_data_quality / 100.0,  # Convert to 0-1 scale
                    data_type="NUMERIC",
                    comment=f"Average data quality score across {results_count} results"
                )
            
            score_current_trace(
                name="top_result_quality",
                value=top_relevance,
                data_type="NUMERIC",
                comment="Relevance score of top search result"
            )
            
            if top_data_quality > 0:
                score_current_trace(
                    name="top_result_data_quality",
                    value=top_data_quality,
                    data_type="NUMERIC",
                    comment="Data quality score of top result"
                )
            
            score_current_trace(
                name="top_result_significance",
                value=top_significance_score,
                data_type="NUMERIC",
                comment=f"Performance significance of top result: {top_significance}"
            )
            
            if avg_improvement > 0:
                # Normalize improvement percent to 0-1 scale (assuming max improvement is around 100%)
                normalized_improvement = min(1.0, avg_improvement / 100.0)
                score_current_trace(
                    name="avg_improvement_percent",
                    value=normalized_improvement,
                    data_type="NUMERIC",
                    comment=f"Average improvement percentage across results: {avg_improvement:.1f}%"
                )
        
    except Exception as e:
        logger.debug(f"Could not add search scores to trace: {e}")

