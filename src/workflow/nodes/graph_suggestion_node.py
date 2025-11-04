from src.prompt.graph_suggestion_template import graph_suggestion_prompt
from src.utils.llm_helper import invoke_llm
from src.workflow.state import ProcessingState
from src.formatter.json_helper import clean_json_from_llm_response
from src.utils.clean_logger import CleanLogger
import json

def graph_suggestion_node(state: ProcessingState) -> ProcessingState:
    """Node for LLM-driven graph suggestions with specific chart data"""
    logger = CleanLogger("workflow.nodes.graph_suggestion")
    
    try:
        state["current_step"] = "graph_suggestion"
        
        if not state.get("analysis_result"):
            logger.graph_error("No analysis result available for graph suggestions")
            state["errors"].append("No analysis result available for graph suggestions")
            return state
        
        analysis_data = state["analysis_result"]
        
        # Get trace_id for Langfuse tracking
        trace_id = state.get("_langfuse_trace_id")
        
        # Create span for graph suggestion node
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name="graph_suggestion_node",
                    trace_id=trace_id,
                    input_data={"has_analysis": True},
                    metadata={"node": "graph_suggestion", "step": "graph_suggestion"}
                )
            except Exception as e:
                logger.warning(f"Failed to create graph suggestion span: {e}")
        
        logger.graph_generation(0, ["LLM-driven suggestions"])
        
        # Get complete chart suggestions from LLM (including chart data)
        prompt_template = graph_suggestion_prompt()
        prompt = prompt_template.format(analysis_data=json.dumps(analysis_data, indent=2))
        
        # Get Langfuse trace_id for observability
        trace_id = state.get("_langfuse_trace_id")
        
        # Get LLM response (prefer structured JSON)
        logger.llm_request("gemini", "graph_suggestion")
        suggestions = invoke_llm(
            prompt,
            as_json=True,
            trace_id=trace_id,
            generation_name="graph_suggestion",
            metadata={"step": "graph_suggestion", "node": "graph_suggestion_node"}
        )
        
        # Handle list return or None
        if isinstance(suggestions, list):
            suggestions = suggestions[0] if suggestions else None
        if not isinstance(suggestions, dict) or not suggestions:
            # Fallback: use centralized JSON cleaning function from raw response
            raw_response = invoke_llm(
                prompt,
                as_json=False,
                trace_id=trace_id,
                generation_name="graph_suggestion_fallback",
                metadata={"step": "graph_suggestion", "fallback": True}
            )
            suggestions = clean_json_from_llm_response(raw_response)
        
        if not suggestions:
            # One retry with stricter instruction
            retry_prompt = prompt + "\n\nReturn ONLY valid JSON that matches the required structure. No markdown, no code fences."
            logger.llm_request("gemini", "graph_suggestion_retry")
            retry_raw = invoke_llm(
                retry_prompt,
                as_json=False,
                trace_id=trace_id,
                generation_name="graph_suggestion_retry",
                metadata={"step": "graph_suggestion", "retry": True}
            )
            suggestions = clean_json_from_llm_response(retry_raw)
        
        if not suggestions:
            logger.graph_error("Failed to parse JSON from LLM response (after retry)")
            raise ValueError("Could not parse JSON from LLM response")
        
        if suggestions and "suggested_charts" in suggestions:
            state["graph_suggestions"] = suggestions
            chart_count = len(suggestions["suggested_charts"])
            chart_types = [chart.get('chart_type', 'unknown') for chart in suggestions["suggested_charts"]]
            logger.graph_generation(chart_count, chart_types)
            
            # Update span with output data
            if trace_id:
                try:
                    from src.utils.langfuse_helper import create_span
                    create_span(
                        name="graph_suggestion_node",
                        trace_id=trace_id,
                        output_data={
                            "chart_count": chart_count,
                            "chart_types": chart_types,
                            "generation_success": True
                        },
                        metadata={"node": "graph_suggestion", "step": "graph_suggestion", "status": "success"}
                    )
                except Exception:
                    pass
        else:
            logger.graph_fallback("LLM failed to generate graph suggestions")
            state["errors"].append("LLM failed to generate graph suggestions")
            # Fallback to basic charts
            state["graph_suggestions"] = _generate_fallback_charts(analysis_data)
            
            # Update span with output data (fallback case)
            if trace_id:
                try:
                    from src.utils.langfuse_helper import create_span
                    create_span(
                        name="graph_suggestion_node",
                        trace_id=trace_id,
                        output_data={"generation_success": False, "used_fallback": True},
                        metadata={"node": "graph_suggestion", "step": "graph_suggestion", "status": "fallback"},
                        level="WARNING"
                    )
                except Exception:
                    pass
        
        return state
        
    except Exception as e:
        logger.graph_error(f"Graph generation failed: {str(e)}")
        state["errors"].append(f"Graph suggestion failed: {str(e)}")
        # Fallback to ensure we always have some charts
        state["graph_suggestions"] = _generate_fallback_charts(state.get("analysis_result", {}))
        return state


def _generate_fallback_charts(analysis_data: dict) -> dict:
    """Generate basic fallback charts if LLM fails"""
    perf_analysis = analysis_data.get("performance_analysis", {})
    calculated = perf_analysis.get("calculated_metrics", {})
    raw_data = perf_analysis.get("raw_data", {})
    
    control_data = raw_data.get("control", {})
    leads_data = raw_data.get("leads_agri", {})
    
    improvement = calculated.get("improvement_percent", 0)
    
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