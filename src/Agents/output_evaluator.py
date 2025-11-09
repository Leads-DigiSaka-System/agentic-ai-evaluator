from src.utils.llm_helper import invoke_llm
from src.utils.clean_logger import get_clean_logger
from src.utils.config import LANGFUSE_CONFIGURED

# CrewAI Integration with Feature Flag
USE_CREWAI = True  # Multi-agent evaluation enabled! 🚀

if USE_CREWAI:
    try:
        from src.Agents.evaluation_crew import validate_output_with_crew
        CREWAI_AVAILABLE = True
    except ImportError as e:
        CREWAI_AVAILABLE = False
        print(f"Warning: CrewAI not available, falling back to single agent: {e}")
else:
    CREWAI_AVAILABLE = False

# Import Langfuse decorator if available
if LANGFUSE_CONFIGURED:
    try:
        from langfuse import observe
        from src.monitoring.trace.langfuse_helper import get_langfuse_client
        LANGFUSE_AVAILABLE = True
    except ImportError:
        LANGFUSE_AVAILABLE = False
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def get_langfuse_client():
            return None
else:
    LANGFUSE_AVAILABLE = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def get_langfuse_client():
        return None


@observe(name="output_evaluator_agent")
def validate_output(state: dict) -> dict:
    """
    ENHANCED INTELLIGENT QUALITY EVALUATOR AGENT
    
    Purpose: Use LLM (single or multi-agent via CrewAI) to assess if outputs meet quality standards
    This is a proper agent that evaluates quality and returns assessment
    The routing decision is made by evaluation_node based on this assessment
    
    NEW: Supports both single agent (fallback) and CrewAI multi-agent evaluation
    Interface remains exactly the same for backward compatibility
    
    Returns quality metrics that evaluation_node uses to set flags
    """
    logger = get_clean_logger(__name__)
    
    try:
        # Log agent start for tracing
        logger.agent_start("output_evaluator_agent", "Starting quality evaluation")
        
        # Update Langfuse trace with enhanced agent metadata
        if LANGFUSE_AVAILABLE:
            client = get_langfuse_client()
            if client:
                try:
                    client.update_current_observation(
                        metadata={
                            "agent": "output_evaluator",
                            "agent_type": "multi_agent_crew" if CREWAI_AVAILABLE and USE_CREWAI else "single_quality_assessor",
                            "step": "evaluation",
                            "evaluation_mode": "crewai" if CREWAI_AVAILABLE and USE_CREWAI else "single_agent",
                            "crewai_enabled": USE_CREWAI,
                            "crewai_available": CREWAI_AVAILABLE
                        }
                    )
                except Exception:
                    pass  # Silently fail if not in observation context
        # DECISION POINT: Use CrewAI multi-agent or single agent evaluation
        if CREWAI_AVAILABLE and USE_CREWAI:
            logger.info("🤖 Using CrewAI multi-agent evaluation system")
            result = validate_output_with_crew(state)
            
        else:
            if USE_CREWAI:
                logger.warning("⚠️ CrewAI requested but not available, falling back to single agent")
            else:
                logger.info("🔧 Using single agent evaluation (CrewAI disabled)")
            
            result = _single_agent_evaluation(state)
        
        # Validate result structure (same for both modes)
        result = _validate_evaluation_result(result)
        
        # Log completion
        evaluation_mode = "CrewAI multi-agent" if (CREWAI_AVAILABLE and USE_CREWAI) else "Single agent"
        # ============================================
        # ENHANCED SCORING ANALYSIS & COMPARISON
        # ============================================
        confidence = result['confidence']
        decision = result['decision']
        
        # Log detailed scoring analysis
        if confidence >= 0.8:
            quality_level = "EXCELLENT 🌟"
        elif confidence >= 0.6:
            quality_level = "GOOD ✅"
        elif confidence >= 0.4:
            quality_level = "MODERATE ⚠️"
        else:
            quality_level = "LOW ❌"
            
        logger.agent_success(
            "output_evaluator_agent", 
            f"Evaluation complete ({evaluation_mode}) - Quality: {quality_level} (confidence: {confidence:.3f}), Decision: {decision}"
        )
        
        # Enhanced scoring context for analysis
        logger.info(f"📊 {evaluation_mode.upper()} Scoring: confidence={confidence:.3f}, decision={decision}, issue={result['issue_type']}")
        
        # Log evaluation mode advantages
        if evaluation_mode == "CrewAI multi-agent":
            logger.info("🤖 Multi-Agent Advantages: 4 specialist perspectives, collaborative decision-making, comprehensive analysis")
        else:
            logger.info("🔧 Single-Agent Mode: Fast evaluation, consistent scoring, direct assessment")
        
        # Update Langfuse with final results
        if LANGFUSE_AVAILABLE:
            client = get_langfuse_client()
            if client:
                try:
                    client.update_current_observation(
                        metadata={
                            "evaluation_confidence": result["confidence"],
                            "evaluation_decision": result["decision"],
                            "issue_type": result["issue_type"],
                            "evaluation_mode": evaluation_mode
                        }
                    )
                except Exception:
                    pass  # Silently fail if not in observation context
        
        return result

    except Exception as e:
        logger.agent_error("output_evaluator_agent", f"Quality validation failed: {str(e)}")
        
        # Update Langfuse with error
        if LANGFUSE_AVAILABLE:
            from src.monitoring.trace.langfuse_helper import update_trace_with_error
            update_trace_with_error(e, {"agent": "output_evaluator", "step": "evaluation"})
        
        return {
            "confidence": 0.5,
            "feedback": f"Validation error: {str(e)[:100]}",
            "decision": "store",
            "issue_type": "no_issue"
        }


def _single_agent_evaluation(state: dict) -> dict:
    """
    Original single agent evaluation logic (moved from main function)
    This is the fallback when CrewAI is not available or disabled
    """
    logger = get_clean_logger(__name__)
    
    try:
        # Extract state data (original logic)
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
        # BUILD CONTEXT-SPECIFIC EVALUATION PROMPT (Single Agent Mode)
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
        # GET LLM QUALITY ASSESSMENT (Single Agent Mode)
        # ============================================
        
        logger.llm_request("single_evaluator_agent", f"Evaluating {evaluation_context} quality")
        result = invoke_llm(prompt, as_json=True)
        logger.llm_response("single_evaluator_agent", "received", "Quality assessment received")
        
        return result

    except Exception as e:
        logger.agent_error("single_evaluator_agent", f"Single agent quality validation failed: {str(e)}")
        
        # Return fallback result
        return {
            "confidence": 0.5,
            "feedback": f"Single agent validation error: {str(e)[:100]}",
            "decision": "store",
            "issue_type": "no_issue"
        }


def _validate_evaluation_result(result: dict) -> dict:
    """
    Validate and sanitize evaluation result to ensure system compatibility
    Works for both single agent and CrewAI results
    """
    logger = get_clean_logger(__name__)
    
    # Handle potential list returns from LLM
    if isinstance(result, list):
        logger.warning("Evaluation returned list, extracting first element")
        result = result[0] if result else {}
    
    # Validate result structure
    if not result or not isinstance(result, dict):
        logger.warning("Invalid evaluation response structure, using defaults")
        return {
            "confidence": 0.5,
            "feedback": "Evaluation returned invalid response structure",
            "decision": "store",
            "issue_type": "no_issue"
        }
    
    # Ensure required fields exist
    result.setdefault("confidence", 0.5)
    result.setdefault("feedback", "No feedback provided")
    result.setdefault("decision", "store")
    result.setdefault("issue_type", "no_issue")
    
    # Validate confidence range
    try:
        conf = float(result["confidence"])
        if not (0.0 <= conf <= 1.0):
            logger.warning(f"Confidence out of range: {conf}, clamping to valid range")
            result["confidence"] = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        logger.warning(f"Invalid confidence value: {result['confidence']}, using 0.5")
        result["confidence"] = 0.5
    
    # Validate decision options
    valid_decisions = ["store", "re_analyze", "suggest_graphs"]
    if result["decision"] not in valid_decisions:
        logger.warning(f"Invalid decision: {result['decision']}, using 'store'")
        result["decision"] = "store"
    
    # Validate issue type
    valid_issues = ["fixable_analysis", "source_limitation", "graph_issue", "no_issue"]
    if result["issue_type"] not in valid_issues:
        logger.warning(f"Invalid issue_type: {result['issue_type']}, using 'no_issue'")
        result["issue_type"] = "no_issue"
    
    # Ensure feedback is string and reasonable length
    if not isinstance(result["feedback"], str):
        result["feedback"] = str(result["feedback"])
    result["feedback"] = result["feedback"][:500]  # Limit length
    
    return result