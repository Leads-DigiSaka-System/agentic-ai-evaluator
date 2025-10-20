from src.prompt.graph_suggestion_template import graph_suggestion_prompt
from src.utils.llm_helper import invoke_llm
from src.workflow.state import ProcessingState
import json

def graph_suggestion_node(state: ProcessingState) -> ProcessingState:
    """Node for LLM-driven graph suggestions with specific chart data"""
    try:
        state["current_step"] = "graph_suggestion"
        
        if not state.get("analysis_result"):
            state["errors"].append("No analysis result available for graph suggestions")
            return state
        
        analysis_data = state["analysis_result"]
        
        print("📊 Generating LLM-driven graph suggestions with specific chart data...")
        
        # Get complete chart suggestions from LLM (including chart data)
        prompt_template = graph_suggestion_prompt()
        prompt = prompt_template.format(analysis_data=json.dumps(analysis_data, indent=2))
        
        suggestions = invoke_llm(prompt, as_json=True)
        
        if suggestions and "suggested_charts" in suggestions:
            state["graph_suggestions"] = suggestions
            chart_count = len(suggestions["suggested_charts"])
            print(f"✅ Generated {chart_count} LLM-driven chart suggestions")
            
            # Log the specific charts generated
            for chart in suggestions["suggested_charts"]:
                print(f"   📈 {chart['chart_type']}: {chart['title']}")
        else:
            state["errors"].append("LLM failed to generate graph suggestions")
            # Fallback to basic charts
            state["graph_suggestions"] = _generate_fallback_charts(analysis_data)
        
        return state
        
    except Exception as e:
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