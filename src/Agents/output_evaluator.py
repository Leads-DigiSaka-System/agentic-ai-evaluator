# file: src/agent/output_evaluator.py

from src.utils.llm_helper import invoke_llm


def validate_output(state: dict) -> dict:
    """
    Evaluate if the output of the workflow (analysis + graphs)
    meets the user's goal and is ready for storage.

    This acts as a post-workflow reasoning layer.
    """

    try:
        # --- Get data from state ---
        analysis = state.get("analysis_result", {})
        graphs = state.get("graph_suggestions", {})
        errors = state.get("errors", [])

        # --- Build prompt ---
        prompt = f"""
        You are an AI validation agent for an agricultural data workflow.
        Your task is to check whether the workflow's output meets the user's goal
        of generating a complete and meaningful analysis report with proper charts.

        Evaluate the following:
        - Are the analysis results coherent and data-driven?
        - Are the generated graphs consistent with the analysis?
        - Are there any errors reported?

        ANALYSIS EXECUTIVE SUMMARY:
        {analysis.get("executive_summary", "N/A")}

        METRICS SUMMARY:
        {analysis.get("performance_analysis", {}).get("calculated_metrics", {})}

        GRAPH TITLES:
        {[chart.get('title', 'Untitled') for chart in graphs.get('suggested_charts', [])]}

        ERRORS:
        {errors}

        Respond in valid JSON:
        {{
            "confidence": 0.0-1.0 float (your confidence that the output meets the goal),
            "feedback": "short reasoning why you chose this rating",
            "decision": "store" or "re_analyze"
        }}

        Rules:
        - If errors exist → confidence < 0.5 and decision = "re_analyze"
        - If analysis and graphs look consistent → confidence > 0.8 and decision = "store"
        - Otherwise → confidence around 0.5 and decision = "re_analyze"
        """

        # --- Run reasoning through LLM ---
        result = invoke_llm(prompt, as_json=True)

        # --- Validate structure ---
        if not result or "decision" not in result:
            return {
                "confidence": 0.5,
                "feedback": "No valid LLM output; defaulting to store.",
                "decision": "store"
            }

        return result

    except Exception as e:
        return {
            "confidence": 0.0,
            "feedback": f"Validation failed: {str(e)}",
            "decision": "re_analyze"
        }
