from src.prompt.graph_suggestion_template import graph_suggestion_prompt
from src.utils.llm_helper import ainvoke_llm
from src.workflow.state import ProcessingState
from src.formatter.json_helper import clean_json_from_llm_response
from src.utils.clean_logger import CleanLogger
from src.utils.config import LANGFUSE_CONFIGURED
import asyncio
import json

# Import Langfuse decorator if available (v3 API)
if LANGFUSE_CONFIGURED:
    try:
        from langfuse import observe, get_client
        LANGFUSE_AVAILABLE = True
    except ImportError:
        LANGFUSE_AVAILABLE = False
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
else:
    LANGFUSE_AVAILABLE = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@observe(name="graph_suggestion_generation")
async def graph_suggestion_node(state: ProcessingState) -> ProcessingState:
    """Node for LLM-driven graph suggestions with specific chart data (v3 API)
    
    ✅ MULTI-USER READY: Now async with ainvoke_llm() for non-blocking concurrent requests.
    """
    logger = CleanLogger("workflow.nodes.graph_suggestion")
    
    try:
        state["current_step"] = "graph_suggestion"
        
        if not state.get("analysis_result"):
            logger.graph_error("No analysis result available for graph suggestions")
            state["errors"].append("No analysis result available for graph suggestions")
            return state
        
        analysis_data = state["analysis_result"]
        
        # Log input metadata to Langfuse (v3 API)
        # ✅ Include user_id for multi-user tracking and isolation
        if LANGFUSE_AVAILABLE:
            try:
                client = get_client()
                if client:
                    metadata = {
                        "has_analysis": True,
                        "product_category": analysis_data.get("product_category", "unknown"),
                        "metrics_count": len(analysis_data.get("metrics_detected", []))
                    }
                    # Add user_id to metadata for better tracking and filtering
                    user_id = state.get("_user_id")
                    if user_id:
                        metadata["user_id"] = user_id
                    client.update_current_observation(metadata=metadata)
            except Exception as e:
                logger.debug(f"Could not update observation: {e}")
        
        logger.graph_generation(0, ["LLM-driven suggestions"])
        
        # Get complete chart suggestions from LLM (including chart data)
        prompt_template = graph_suggestion_prompt()
        
        # Safely format the prompt with error handling
        try:
            analysis_json = json.dumps(analysis_data, indent=2)
            # Limit analysis data size to prevent prompt overflow
            if len(analysis_json) > 30000:
                logger.debug(f"Analysis data too large ({len(analysis_json)} chars), truncating...")
                analysis_json = analysis_json[:30000] + "\n... (truncated for prompt size)"
            prompt = prompt_template.format(analysis_data=analysis_json)
        except Exception as e:
            logger.graph_error(f"Failed to format prompt: {str(e)}")
            state["errors"].append(f"Prompt formatting error: {str(e)}")
            state["graph_suggestions"] = _generate_fallback_charts(analysis_data)
            return state
        
        # Get LLM response (prefer structured JSON) - now async
        logger.llm_request("gemini", "graph_suggestion")
        suggestions = await ainvoke_llm(prompt, as_json=True, trace_name="graph_suggestion")
        
        # Handle list return or None
        if isinstance(suggestions, list):
            suggestions = suggestions[0] if suggestions else None
        if not isinstance(suggestions, dict) or not suggestions:
            # Fallback: use centralized JSON cleaning function from raw response
            raw_response = await ainvoke_llm(prompt, as_json=False, trace_name="graph_suggestion_raw")
            suggestions = clean_json_from_llm_response(raw_response)
        
        if not suggestions:
            # One retry with stricter instruction
            retry_prompt = prompt + "\n\nReturn ONLY valid JSON that matches the required structure. No markdown, no code fences."
            logger.llm_request("gemini", "graph_suggestion_retry")
            retry_raw = await ainvoke_llm(retry_prompt, as_json=False, trace_name="graph_suggestion_retry")
            suggestions = clean_json_from_llm_response(retry_raw)
        
        if not suggestions:
            logger.graph_error("Failed to parse JSON from LLM response (after retry)")
            raise ValueError("Could not parse JSON from LLM response")
        
        if suggestions and "suggested_charts" in suggestions:
            state["graph_suggestions"] = suggestions
            chart_count = len(suggestions["suggested_charts"])
            chart_types = [chart.get('chart_type', 'unknown') for chart in suggestions["suggested_charts"]]
            
            logger.graph_generation(chart_count, chart_types)
            
            # Log graph metrics to Langfuse (v3 API)
            # ✅ Include user_id for multi-user tracking and isolation
            if LANGFUSE_AVAILABLE:
                try:
                    client = get_client()
                    if client:
                        metadata = {
                            "chart_count": chart_count,
                            "chart_types": chart_types,
                            "generation_method": "llm"
                        }
                        # Add user_id to metadata for better tracking and filtering
                        user_id = state.get("_user_id")
                        if user_id:
                            metadata["user_id"] = user_id
                        client.update_current_observation(metadata=metadata)
                except Exception as e:
                    logger.debug(f"Could not update observation with metrics: {e}")
        else:
            logger.graph_fallback("LLM failed to generate graph suggestions")
            state["errors"].append("LLM failed to generate graph suggestions")
            # Fallback to basic charts
            state["graph_suggestions"] = _generate_fallback_charts(analysis_data)
            
            if LANGFUSE_AVAILABLE:
                try:
                    client = get_client()
                    if client:
                        client.update_current_observation(
                            metadata={"generation_method": "fallback", "reason": "llm_failed"}
                        )
                except Exception as e:
                    logger.debug(f"Could not update observation: {e}")
        
        return state
        
    except Exception as e:
        logger.graph_error(f"Graph generation failed: {str(e)}")
        state["errors"].append(f"Graph suggestion failed: {str(e)}")
        
        # Log error to Langfuse (v3 API)
        if LANGFUSE_AVAILABLE:
            from src.monitoring.trace.langfuse_helper import update_trace_with_error
            update_trace_with_error(e, {"step": "graph_suggestion"})
        
        # Fallback to ensure we always have some charts
        state["graph_suggestions"] = _generate_fallback_charts(state.get("analysis_result", {}))
        
        if LANGFUSE_AVAILABLE:
            try:
                client = get_client()
                if client:
                    client.update_current_observation(
                        metadata={"generation_method": "fallback", "reason": "exception"}
                    )
            except Exception as e:
                logger.debug(f"Could not update observation: {e}")
        
        return state


def _generate_fallback_charts(analysis_data: dict) -> dict:
    """Generate basic fallback charts if LLM fails"""
    perf_analysis = analysis_data.get("performance_analysis", {})
    calculated = perf_analysis.get("calculated_metrics", {})
    raw_data = perf_analysis.get("raw_data", {})
    
    control_data = raw_data.get("control", {})
    leads_data = raw_data.get("leads_agri", {})
    
    # Try both field names for compatibility
    improvement = calculated.get("relative_improvement_percent", calculated.get("improvement_percent", 0))
    
    fallback_charts = {
        "suggested_charts": [
            {
                "chart_id": "fallback_performance_trend",
                "chart_type": "line_chart",
                "title": f"Performance Trend - {improvement}% Improvement",
                "priority": "high",
                "data_source": "performance_analysis.raw_data",
                "description": "Performance progression over assessment intervals",
                "chart_data": {
                    "labels": list(control_data.keys()),
                    "datasets": [
                        {
                            "label": "Control",
                            "data": list(control_data.values()),
                            "borderColor": "#e74c3c",
                            "backgroundColor": "rgba(231, 76, 60, 0.1)",
                            "tension": 0.1
                        },
                        {
                            "label": "Leads Agri",
                            "data": list(leads_data.values()),
                            "borderColor": "#27ae60", 
                            "backgroundColor": "rgba(39, 174, 96, 0.1)",
                            "tension": 0.1
                        }
                    ]
                },
                "chart_options": {
                    "responsive": True,
                    "plugins": {
                        "legend": {"position": "top"},
                        "title": {
                            "display": True,
                            "text": "Performance Over Time"
                        }
                    },
                    "scales": {
                        "y": {"beginAtZero": True}
                    }
                }
            }
        ],
        "summary": "Basic performance trend chart (fallback)"
    }
    
    return fallback_charts