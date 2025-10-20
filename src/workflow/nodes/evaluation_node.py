from src.Agents.output_evaluator import validate_output

def evaluation_node(state: dict) -> dict:
    """
    Node to evaluate workflow output quality before storage
    """
    print("🔍 Evaluating output quality...")
    
    try:
        # Run output evaluation
        evaluation_result = validate_output(state)
        
        confidence = evaluation_result.get("confidence", 0)
        decision = evaluation_result.get("decision", "store")
        feedback = evaluation_result.get("feedback", "No feedback")
        
        print(f"📊 Output Evaluation: {confidence:.2f} confidence - {decision} - {feedback}")
        
        # Store evaluation results in state
        state["output_evaluation"] = evaluation_result
        
        # If evaluation says to re-analyze, set flag
        if decision == "re_analyze":
            state["needs_reanalysis"] = True
            print("🔄 Output evaluation suggests re-analysis")
        else:
            state["needs_reanalysis"] = False
            print("✅ Output evaluation passed - ready for storage")
            
    except Exception as e:
        print(f"❌ Output evaluation failed: {str(e)}")
        state["errors"].append(f"Output evaluation error: {str(e)}")
        state["output_evaluation"] = {
            "confidence": 0.0,
            "decision": "store",  # Default to store on failure
            "feedback": f"Evaluation failed: {str(e)}"
        }
    
    return state