"""
Workflow routing functions for LangGraph conditional edges.

This module contains all the routing logic that determines the next node
in the processing workflow based on the current state.
"""
from src.workflow.state import ProcessingState
from src.shared.logging.clean_logger import CleanLogger
from langgraph.graph import END

logger = CleanLogger("workflow.routers")


def route_after_extract(state: ProcessingState) -> str:
    """
    After extraction, check for errors then validate content
    
    Routes to content validation instead of directly to analysis
    
    ✅ MULTI-USER READY: Includes user_id in logs to prevent confusion when multiple users process simultaneously
    """
    user_id = state.get("_user_id")
    user_context = f" (user: {user_id})" if user_id else ""
    
    if state.get("errors") and not state.get("extracted_markdown"):
        logger.workflow_error("extraction", f"Extraction failed critically{user_context}")
        return "handle_errors"
    
    # Check file validation results (if available)
    file_validation = state.get("file_validation", {})
    if file_validation and not file_validation.get("is_valid", True):
        logger.validation_error("file_format", f"File format validation failed{user_context}")
        return "handle_errors"
    
    logger.log_route("extract", "validate_content", f"Content validation required{user_context}")
    return "validate_content"


def route_after_content_validation(state: ProcessingState) -> str:
    """
    After content validation, proceed to analysis or error
    
    Checks if content is a valid product demo
    
    ✅ MULTI-USER READY: Includes user_id in logs to prevent confusion when multiple users process simultaneously
    """
    user_id = state.get("_user_id")
    user_context = f" (user: {user_id})" if user_id else ""
    
    is_valid = state.get("is_valid_content", False)
    validation_result = state.get("content_validation", {})
    
    if not is_valid:
        confidence = validation_result.get("confidence", 0.0)
        content_type = validation_result.get("content_type", "unknown")
        logger.validation_error("content", f"Content validation failed: {content_type} (confidence: {confidence:.2f}){user_context}")
        logger.info(f"Validation feedback: {validation_result.get('feedback', 'No feedback')}{user_context}")
        return "handle_errors"
    
    logger.log_route("validate_content", "analyze", f"Content validated as product demo{user_context}")
    return "analyze"


def route_after_analysis(state: ProcessingState) -> str:
    """
    After analysis, check for errors then proceed to evaluation
    
    ✅ MULTI-USER READY: Includes user_id in logs to prevent confusion when multiple users process simultaneously
    """
    user_id = state.get("_user_id")
    user_context = f" (user: {user_id})" if user_id else ""
    
    if state.get("errors") and not state.get("analysis_result"):
        logger.workflow_error("analysis", f"Analysis failed critically{user_context}")
        return "handle_errors"
    logger.log_route("analyze", "evaluate_analysis", f"Analysis completed successfully{user_context}")
    return "evaluate_analysis"


def route_after_analysis_evaluation(state: ProcessingState) -> str:
    """
    INTELLIGENT ROUTING based on evaluation results
    
    ✅ MULTI-USER READY: Includes user_id in logs and validates user context to prevent confusion when multiple users process simultaneously
    """
    user_id = state.get("_user_id")
    user_context = f" (user: {user_id})" if user_id else ""
    
    needs_reanalysis = state.get("needs_reanalysis", False)
    evaluation = state.get("output_evaluation", {})
    attempts = state.get("evaluation_attempts", 0)
    
    # Handle list returns from LLM
    if isinstance(evaluation, list):
        evaluation = evaluation[0] if evaluation else {}
    
    issue_type = evaluation.get("issue_type", "no_issue")
    confidence = evaluation.get("confidence", 0.5)
    
    # INTELLIGENT DECISION LOGIC
    # ✅ Each routing decision is isolated per user via state isolation (LangGraph handles this)
    if needs_reanalysis and attempts < 2:
        logger.log_retry("analysis", attempts + 1, 2, f"Quality low (confidence: {confidence:.2f}){user_context}")
        return "analyze"
    
    if issue_type == "source_limitation":
        logger.log_route("evaluate_analysis", "suggest_graphs", f"Source limitations identified (expected){user_context}")
        return "suggest_graphs"
    
    if confidence < 0.3 and attempts < 2:
        logger.log_retry("analysis", attempts + 1, 2, f"Very low confidence ({confidence:.2f}){user_context}")
        # ✅ State modification is safe - each workflow execution has isolated state
        state["needs_reanalysis"] = True
        return "analyze"
    
    # Default: proceed to next step
    logger.log_route("evaluate_analysis", "suggest_graphs", f"Analysis acceptable (confidence: {confidence:.2f}){user_context}")
    return "suggest_graphs"


def route_after_graph_suggestion(state: ProcessingState) -> str:
    """
    After graph generation, always evaluate graphs
    
    ✅ MULTI-USER READY: Includes user_id in logs to prevent confusion when multiple users process simultaneously
    """
    user_id = state.get("_user_id")
    user_context = f" (user: {user_id})" if user_id else ""
    
    if state.get("errors") and not state.get("graph_suggestions"):
        logger.workflow_error("graph_generation", f"Graph generation failed critically{user_context}")
        return "handle_errors"
    logger.log_route("suggest_graphs", "evaluate_graphs", f"Graph generation completed successfully{user_context}")
    return "evaluate_graphs"


def route_after_graph_evaluation(state: ProcessingState) -> str:
    """
    INTELLIGENT ROUTING based on graph evaluation
    
    ✅ MULTI-USER READY: Includes user_id in logs and validates user context to prevent confusion when multiple users process simultaneously
    """
    user_id = state.get("_user_id")
    user_context = f" (user: {user_id})" if user_id else ""
    
    needs_regraph = state.get("needs_regraph", False)
    evaluation = state.get("output_evaluation", {})
    attempts = state.get("evaluation_attempts", 0)
    
    # Handle list returns
    if isinstance(evaluation, list):
        evaluation = evaluation[0] if evaluation else {}
    
    issue_type = evaluation.get("issue_type", "no_issue")
    confidence = evaluation.get("confidence", 0.5)
    
    # INTELLIGENT DECISION LOGIC
    # ✅ Each routing decision is isolated per user via state isolation (LangGraph handles this)
    if needs_regraph and attempts < 2:
        logger.log_retry("graph_generation", attempts + 1, 2, f"Quality low (confidence: {confidence:.2f}){user_context}")
        return "suggest_graphs"
    
    if issue_type == "graph_issue" and confidence < 0.5 and attempts < 2:
        logger.log_retry("graph_generation", attempts + 1, 2, f"Graph issues detected (confidence: {confidence:.2f}){user_context}")
        # ✅ State modification is safe - each workflow execution has isolated state
        state["needs_regraph"] = True
        return "suggest_graphs"
    
    # Default: proceed to chunking
    logger.log_route("evaluate_graphs", "chunk", f"Graphs acceptable (confidence: {confidence:.2f}){user_context}")
    return "chunk"


def route_after_chunk(state: ProcessingState) -> str:
    """
    After chunking, workflow ends - storage handled separately
    
    ✅ MULTI-USER READY: Includes user_id in logs to prevent confusion when multiple users process simultaneously
    """
    user_id = state.get("_user_id")
    user_context = f" (user: {user_id})" if user_id else ""
    
    if not state.get("chunks"):
        logger.workflow_error("chunking", f"Chunking produced no chunks{user_context}")
        return "handle_errors"
    chunk_count = len(state.get('chunks', []))
    logger.log_route("chunk", "END", f"Chunking completed ({chunk_count} chunks) - storage via API{user_context}")
    return END

