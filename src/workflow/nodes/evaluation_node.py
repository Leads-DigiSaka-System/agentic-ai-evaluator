from src.Agents.output_evaluator import validate_output

def evaluation_node(state: dict) -> dict:
    """
    INTELLIGENT EVALUATION NODE
    
    Purpose: Use LLM to assess output quality and set decision flags
    Philosophy: Intelligence decides "is this good enough?" not "where to go next"
    """
    print("🔍 Evaluating output quality with intelligent reasoning...")
    
    try:
        # Initialize evaluation attempts counter if not exists
        if "evaluation_attempts" not in state:
            state["evaluation_attempts"] = 0
            
        # Determine evaluation context based on what exists
        current_step = state.get("current_step", "unknown")
        has_analysis = bool(state.get("analysis_result"))
        has_graphs = bool(state.get("graph_suggestions"))
        
        # Smart context detection
        if has_analysis and not has_graphs:
            evaluation_context = "analysis"
            state["current_step"] = "evaluate_analysis"
        elif has_graphs:
            evaluation_context = "graphs"
            state["current_step"] = "evaluate_graphs"
        else:
            evaluation_context = "unknown"
            state["current_step"] = "evaluation"
        
        print(f"📋 Evaluation context: {evaluation_context}")
            
        # Run intelligent output evaluation (LLM-based quality assessment)
        evaluation_result = validate_output(state)
        
        # Handle potential list returns from LLM
        if isinstance(evaluation_result, list):
            evaluation_result = evaluation_result[0] if evaluation_result else {}
        
        # Extract evaluation metrics
        confidence = evaluation_result.get("confidence", 0.5)
        decision = evaluation_result.get("decision", "store")
        feedback = evaluation_result.get("feedback", "No feedback")
        issue_type = evaluation_result.get("issue_type", "no_issue")
        
        print(f"📊 {evaluation_context.upper()} Evaluation Results:")
        print(f"   ├─ Confidence: {confidence:.2f}")
        print(f"   ├─ Decision: {decision}")
        print(f"   ├─ Issue Type: {issue_type}")
        print(f"   └─ Feedback: {feedback[:100]}...")
        
        # Store evaluation results
        state["output_evaluation"] = evaluation_result
        
        # ============================================
        # INTELLIGENT DECISION LOGIC
        # Sets flags that router will respect
        # ============================================
        
        if evaluation_context == "analysis":
            # Evaluating ANALYSIS quality
            print("\n🧠 Analysis Evaluation Decision:")
            
            if issue_type == "source_limitation":
                # Data missing from source - this is EXPECTED, not an error
                state["needs_reanalysis"] = False
                state["needs_regraph"] = False
                print("   ✅ Source limitations identified (expected) - will proceed")
                
            elif issue_type == "fixable_analysis":
                # Analysis has fixable issues
                if confidence < 0.4 and state["evaluation_attempts"] < 2:
                    state["needs_reanalysis"] = True
                    state["needs_regraph"] = False
                    state["evaluation_attempts"] += 1
                    print(f"   🔄 Quality too low (conf: {confidence:.2f}) - RETRY #{state['evaluation_attempts']}")
                else:
                    state["needs_reanalysis"] = False
                    state["needs_regraph"] = False
                    if state["evaluation_attempts"] >= 2:
                        print(f"   ⚠️ Max retries reached - ACCEPTING with confidence {confidence:.2f}")
                    else:
                        print(f"   ✅ Acceptable quality (conf: {confidence:.2f}) - PROCEED")
            else:
                # No issues
                state["needs_reanalysis"] = False
                state["needs_regraph"] = False
                print(f"   ✅ Analysis passed evaluation (conf: {confidence:.2f}) - PROCEED")
                
        elif evaluation_context == "graphs":
            # Evaluating GRAPH quality
            print("\n🧠 Graph Evaluation Decision:")
            
            if issue_type == "graph_issue":
                # Graphs have issues
                if confidence < 0.7 and state["evaluation_attempts"] < 2:
                    state["needs_reanalysis"] = False
                    state["needs_regraph"] = True
                    state["evaluation_attempts"] += 1
                    print(f"   🔄 Graph quality low (conf: {confidence:.2f}) - REGENERATE #{state['evaluation_attempts']}")
                else:
                    state["needs_reanalysis"] = False
                    state["needs_regraph"] = False
                    if state["evaluation_attempts"] >= 2:
                        print(f"   ⚠️ Max retries reached - ACCEPTING graphs with confidence {confidence:.2f}")
                    else:
                        print(f"   ✅ Acceptable graphs (conf: {confidence:.2f}) - PROCEED")
            else:
                # No issues
                state["needs_reanalysis"] = False
                state["needs_regraph"] = False
                print(f"   ✅ Graphs passed evaluation (conf: {confidence:.2f}) - PROCEED")
        
        else:
            # Unknown context - safe defaults
            state["needs_reanalysis"] = False
            state["needs_regraph"] = False
            print("   ⚠️ Unknown evaluation context - proceeding with defaults")
        
        # Add evaluation summary to state for visibility
        state["last_evaluation_summary"] = {
            "context": evaluation_context,
            "confidence": confidence,
            "decision": decision,
            "issue_type": issue_type,
            "attempts": state["evaluation_attempts"]
        }
            
    except Exception as e:
        print(f"❌ Output evaluation failed: {str(e)}")
        state["errors"].append(f"Output evaluation error: {str(e)}")
        
        # Safe fallback on error
        state["output_evaluation"] = {
            "confidence": 0.5,
            "feedback": f"Evaluation failed but proceeding: {str(e)}",
            "decision": "store",
            "issue_type": "no_issue"
        }
        state["needs_reanalysis"] = False
        state["needs_regraph"] = False
        state["current_step"] = "evaluation_failed"
    
    return state