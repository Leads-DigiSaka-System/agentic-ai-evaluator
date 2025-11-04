from src.utils.llm_helper import invoke_llm
from src.utils.clean_logger import get_clean_logger
from typing import Optional

def validate_output(state: dict, trace_id: Optional[str] = None) -> dict:
    """
    INTELLIGENT QUALITY EVALUATOR
    
    Purpose: Use LLM to assess if outputs meet quality standards
    Does NOT decide workflow routing - only quality assessment
    
    Args:
        state: Processing state dictionary
        trace_id: Optional Langfuse trace ID for observability
    
    Returns quality metrics that evaluation_node uses to set flags
    """
    logger = get_clean_logger(__name__)
    
    try:
        # Extract state data
        analysis = state.get("analysis_result", {})
        graphs = state.get("graph_suggestions", {})
        errors = state.get("errors", [])
        extracted_markdown = state.get("extracted_markdown", "")
        
        # Determine what we're evaluating
        has_analysis = bool(analysis)
        has_graphs = bool(graphs)
        
        if has_analysis and not has_graphs:
            evaluation_context = "analysis"
        elif has_graphs:
            evaluation_context = "graphs"
        else:
            evaluation_context = "unknown"
        
        # Get previous attempts for context
        previous_evaluation = state.get("output_evaluation", {})
        if isinstance(previous_evaluation, list):
            previous_evaluation = previous_evaluation[0] if previous_evaluation else {}
        
        previous_confidence = previous_evaluation.get("confidence", None)
        attempts = state.get("evaluation_attempts", 0)
        
        # ============================================
        # BUILD CONTEXT-SPECIFIC EVALUATION PROMPT
        # ============================================
        
        if evaluation_context == "analysis":
            # Focus on ANALYSIS quality
            prompt = f"""
You are a QUALITY ASSESSOR for agricultural data analysis.

YOUR TASK: Evaluate if this analysis meets quality standards for presentation to users.

ANALYSIS SUMMARY:
{analysis.get("executive_summary", "N/A")}

KEY METRICS:
{analysis.get("performance_analysis", {}).get("calculated_metrics", {})}

DATA QUALITY NOTES:
{analysis.get("data_quality", {}).get("reliability_notes", "N/A")}

RELIABILITY ASSESSMENT:
{analysis.get("data_quality", {}).get("reliability_assessment", "N/A")}

EVALUATION CRITERIA:
1. **Completeness**: Does the analysis cover key aspects of the data?
2. **Accuracy**: Are calculations and interpretations correct?
3. **Clarity**: Is the executive summary clear and useful?
4. **Data Handling**: Are missing/incomplete data properly acknowledged?

IMPORTANT DISTINCTIONS:
- "Missing data from source" = source_limitation (NOT a quality issue - accept this)
- "Incorrect calculations" = fixable_analysis (quality issue - needs retry)
- "Unclear summary" = fixable_analysis (quality issue - needs retry)
- "Missing expected fields" = check if it's a source issue or extraction issue

PREVIOUS CONTEXT:
- This is attempt #{attempts + 1}
- Previous confidence: {previous_confidence if previous_confidence else "N/A"}

**CRITICAL: RETURN ONLY JSON, NO OTHER TEXT**
{{
    "confidence": 0.0-1.0,
    "feedback": "Specific evaluation feedback explaining your assessment",
    "decision": "store" or "re_analyze",
    "issue_type": "fixable_analysis" or "source_limitation" or "no_issue"
}}

Guidelines:
- confidence > 0.7 = good quality
- confidence 0.4-0.7 = acceptable (may accept or retry based on attempts)
- confidence < 0.4 = poor quality (should retry if attempts allow)
- Use "source_limitation" when data is inherently missing from input
- Use "fixable_analysis" when the analysis itself can be improved
"""
        
        else:  # graphs evaluation
            # Focus on GRAPH quality
            chart_count = len(graphs.get('suggested_charts', []))
            chart_titles = [chart.get('title', 'Untitled') for chart in graphs.get('suggested_charts', [])]
            chart_data_check = [
                f"Chart {i+1}: {len(chart.get('chart_data', {}).get('datasets', []))} datasets, "
                f"{len(chart.get('chart_data', {}).get('labels', []))} labels"
                for i, chart in enumerate(graphs.get('suggested_charts', []))
            ]
            
            prompt = f"""
You are a QUALITY ASSESSOR for data visualization suggestions.

YOUR TASK: Evaluate if these graph suggestions are appropriate and useful.

ANALYSIS CONTEXT:
{analysis.get("executive_summary", "N/A")[:300]}...

GRAPH SUGGESTIONS:
- Number of charts: {chart_count}
- Chart titles: {chart_titles}
- Data validation: {chart_data_check}

EVALUATION CRITERIA:
1. **Appropriateness**: Do chart types match the data being visualized?
2. **Completeness**: Are there enough charts to tell the story?
3. **Data Quality**: Do charts have proper datasets and labels?
4. **Clarity**: Are titles and descriptions meaningful?
5. **Relevance**: Do graphs highlight key insights from analysis?

COMMON ISSUES TO CHECK:
- Empty or missing datasets
- Mismatched chart types (e.g., pie chart for time series)
- Unclear or generic titles
- Missing labels or legends
- Graphs that don't relate to analysis findings

PREVIOUS CONTEXT:
- This is attempt #{attempts + 1}
- Previous confidence: {previous_confidence if previous_confidence else "N/A"}

**CRITICAL: RETURN ONLY JSON, NO OTHER TEXT**
{{
    "confidence": 0.0-1.0,
    "feedback": "Specific evaluation of graph quality and appropriateness",
    "decision": "store" or "suggest_graphs",
    "issue_type": "graph_issue" or "no_issue"
}}

Guidelines:
- confidence > 0.7 = good graphs
- confidence 0.5-0.7 = acceptable (may proceed or regenerate based on attempts)
- confidence < 0.5 = poor graphs (should regenerate if attempts allow)
"""
        
        # ============================================
        # GET LLM QUALITY ASSESSMENT
        # ============================================
        
        result = invoke_llm(
            prompt,
            as_json=True,
            trace_id=trace_id,
            generation_name=f"output_evaluation_{evaluation_context}",
            metadata={
                "step": "output_evaluation",
                "evaluation_context": evaluation_context,
                "attempts": attempts
            }
        )
        
        # Handle potential list returns
        if isinstance(result, list):
            logger.warning("LLM returned list, extracting first element")
            result = result[0] if result else {}
        
        # Validate result structure
        if not result or not isinstance(result, dict):
            logger.warning("Invalid LLM response structure, using defaults")
            return {
                "confidence": 0.5,
                "feedback": "LLM returned invalid response structure",
                "decision": "store",
                "issue_type": "no_issue"
            }
        
        # Ensure required fields exist
        result.setdefault("confidence", 0.5)
        result.setdefault("feedback", "No feedback provided")
        result.setdefault("decision", "store")
        result.setdefault("issue_type", "no_issue")
        
        # Validate confidence range
        if not (0.0 <= result["confidence"] <= 1.0):
            logger.warning(f"Invalid confidence value: {result['confidence']}, clamping to 0.5")
            result["confidence"] = 0.5
        
        return result

    except Exception as e:
        logger.error(f"Quality validation failed: {str(e)}")
        return {
            "confidence": 0.5,
            "feedback": f"Validation error: {str(e)}",
            "decision": "store",
            "issue_type": "no_issue"
        }