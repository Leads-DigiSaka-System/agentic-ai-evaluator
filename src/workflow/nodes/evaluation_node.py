from src.Agents.output_evaluator import validate_output
from src.utils.clean_logger import CleanLogger

def evaluation_node(state: dict) -> dict:
    """
    INTELLIGENT EVALUATION NODE
    
    Purpose: Use LLM to assess output quality and set decision flags
    Philosophy: Intelligence decides "is this good enough?" not "where to go next"
    """
    logger = CleanLogger("workflow.nodes.evaluation")
    
    logger.workflow_start("output_evaluation", "Intelligent quality assessment")
    
    # Get trace_id for Langfuse tracking
    trace_id = state.get("_langfuse_trace_id")
    
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
            span_name = "evaluation_analysis_node"
        elif has_graphs:
            evaluation_context = "graphs"
            state["current_step"] = "evaluate_graphs"
            span_name = "evaluation_graphs_node"
        else:
            evaluation_context = "unknown"
            state["current_step"] = "evaluation"
            span_name = "evaluation_node"
        
        logger.log_decision("evaluation_context", evaluation_context, f"Current step: {current_step}")
        
        # Create span for evaluation node
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name=span_name,
                    trace_id=trace_id,
                    input_data={
                        "has_analysis": has_analysis,
                        "has_graphs": has_graphs,
                        "evaluation_context": evaluation_context
                    },
                    metadata={"node": "evaluation", "step": "output_evaluation", "context": evaluation_context}
                )
            except Exception as e:
                logger.warning(f"Failed to create evaluation span: {e}")
            
        # Run intelligent output evaluation (LLM-based quality assessment)
        logger.agent_start("output_evaluator", f"Evaluating {evaluation_context}")
        evaluation_result = validate_output(state, trace_id=trace_id)
        
        # Handle potential list returns from LLM
        if isinstance(evaluation_result, list):
            evaluation_result = evaluation_result[0] if evaluation_result else {}
        
        # Extract evaluation metrics
        confidence = evaluation_result.get("confidence", 0.5)
        decision = evaluation_result.get("decision", "store")
        feedback = evaluation_result.get("feedback", "No feedback")
        issue_type = evaluation_result.get("issue_type", "no_issue")
        
        logger.agent_success("output_evaluator", f"Confidence: {confidence:.2f}, Decision: {decision}")
        logger.info(f"Issue Type: {issue_type}")
        logger.info(f"Feedback: {feedback[:100]}...")
        
        # Store evaluation results
        state["output_evaluation"] = evaluation_result
        
        # ============================================
        # INTELLIGENT DECISION LOGIC
        # Sets flags that router will respect
        # ============================================
        
        if evaluation_context == "analysis":
            # Evaluating ANALYSIS quality
            logger.log_decision("analysis_evaluation", "Starting analysis evaluation decision")
            
            if issue_type == "source_limitation":
                # Data missing from source - this is EXPECTED, not an error
                state["needs_reanalysis"] = False
                state["needs_regraph"] = False
                logger.log_decision("analysis_evaluation", "Source limitations identified (expected) - will proceed")
                
            elif issue_type == "fixable_analysis":
                # Analysis has fixable issues
                if confidence < 0.4 and state["evaluation_attempts"] < 2:
                    state["needs_reanalysis"] = True
                    state["needs_regraph"] = False
                    state["evaluation_attempts"] += 1
                    logger.log_retry("analysis", state["evaluation_attempts"], 2, f"Quality too low (conf: {confidence:.2f})")
                else:
                    state["needs_reanalysis"] = False
                    state["needs_regraph"] = False
                    if state["evaluation_attempts"] >= 2:
                        logger.log_decision("analysis_evaluation", f"Max retries reached - ACCEPTING with confidence {confidence:.2f}")
                    else:
                        logger.log_decision("analysis_evaluation", f"Acceptable quality (conf: {confidence:.2f}) - PROCEED")
            else:
                # No issues
                state["needs_reanalysis"] = False
                state["needs_regraph"] = False
                logger.log_decision("analysis_evaluation", f"Analysis passed evaluation (conf: {confidence:.2f}) - PROCEED")
                
        elif evaluation_context == "graphs":
            # Evaluating GRAPH quality
            logger.log_decision("graph_evaluation", "Starting graph evaluation decision")
            
            if issue_type == "graph_issue":
                # Graphs have issues
                if confidence < 0.7 and state["evaluation_attempts"] < 2:
                    state["needs_reanalysis"] = False
                    state["needs_regraph"] = True
                    state["evaluation_attempts"] += 1
                    logger.log_retry("graph_generation", state["evaluation_attempts"], 2, f"Quality low (conf: {confidence:.2f})")
                else:
                    state["needs_reanalysis"] = False
                    state["needs_regraph"] = False
                    if state["evaluation_attempts"] >= 2:
                        logger.log_decision("graph_evaluation", f"Max retries reached - ACCEPTING graphs with confidence {confidence:.2f}")
                    else:
                        logger.log_decision("graph_evaluation", f"Acceptable graphs (conf: {confidence:.2f}) - PROCEED")
            else:
                # No issues
                state["needs_reanalysis"] = False
                state["needs_regraph"] = False
                logger.log_decision("graph_evaluation", f"Graphs passed evaluation (conf: {confidence:.2f}) - PROCEED")
        
        else:
            # Unknown context - safe defaults
            state["needs_reanalysis"] = False
            state["needs_regraph"] = False
            logger.log_decision("evaluation", "Unknown evaluation context - proceeding with defaults")
        
        # Add evaluation summary to state for visibility
        state["last_evaluation_summary"] = {
            "context": evaluation_context,
            "confidence": confidence,
            "decision": decision,
            "issue_type": issue_type,
            "attempts": state["evaluation_attempts"]
        }
        
        logger.workflow_success("output_evaluation", f"Evaluation completed for {evaluation_context}")
        
        # Update span with output data
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name=span_name,
                    trace_id=trace_id,
                    output_data={
                        "confidence": confidence,
                        "decision": decision,
                        "issue_type": issue_type,
                        "attempts": state["evaluation_attempts"]
                    },
                    metadata={"node": "evaluation", "step": "output_evaluation", "status": "success"}
                )
            except Exception:
                pass
            
    except Exception as e:
        logger.workflow_error("output_evaluation", str(e))
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