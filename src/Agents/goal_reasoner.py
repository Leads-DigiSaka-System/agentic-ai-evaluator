# file: src/agent/goal_reasoner.py

from src.utils.llm_helper import invoke_llm


def goal_reasoner(state: dict) -> dict:
    """
    Enhanced goal reasoner that considers output evaluation
    """
    try:
        # Check if we have output evaluation results
        output_eval = state.get("output_evaluation", {})
        needs_reanalysis = state.get("needs_reanalysis", False)
        current_step = state.get("current_step", "unknown")
        
        # Build enhanced reasoning prompt
        prompt = f"""
        You are an AI goal reasoner managing a document analysis pipeline.
        
        Current state summary:
        - Current step: {current_step}
        - Has extracted_markdown: {bool(state.get("extracted_markdown"))}
        - Has analysis_result: {bool(state.get("analysis_result"))}
        - Has graph_suggestions: {bool(state.get("graph_suggestions"))}
        - Output evaluation confidence: {output_eval.get('confidence', 'N/A')}
        - Output evaluation decision: {output_eval.get('decision', 'N/A')}
        - Needs reanalysis: {needs_reanalysis}
        - Errors: {state.get("errors", [])}

        Enhanced Rules:
        - If we just completed graph suggestions AND haven't evaluated yet → choose "evaluate"
        - If output evaluation suggests re_analyze OR confidence < 0.7 → choose "analyze"
        - If extraction failed or missing → choose "extract"
        - If extracted but no analysis → choose "analyze" 
        - If analyzed but no graphs → choose "suggest_graphs"
        - If evaluation passed (confidence > 0.7) and no errors → choose "chunk"
        - If errors are found → choose "retry"
        - After chunking, if successful → choose "store"

        Current Step Context: {current_step}

        Available actions: extract|analyze|suggest_graphs|evaluate|chunk|store|retry

        Respond in valid JSON:
        {{
            "next_action": "extract|analyze|suggest_graphs|evaluate|chunk|store|retry",
            "reason": "short reasoning why you chose that action"
        }}
        """

        response = invoke_llm(prompt, as_json=True)

        if not response or "next_action" not in response:
            return {
                "next_action": "retry",
                "reason": "No valid LLM response; defaulting to retry."
            }

        return response

    except Exception as e:
        return {
            "next_action": "retry", 
            "reason": f"Goal Reasoner exception: {str(e)}"
        }