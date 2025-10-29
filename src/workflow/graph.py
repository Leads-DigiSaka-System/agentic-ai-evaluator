from langgraph.graph import StateGraph, END
from src.workflow.state import ProcessingState
from src.workflow.nodes.nodes import extraction_node, analysis_node, chunking_node, error_node
from src.workflow.nodes.graph_suggestion_node import graph_suggestion_node
from src.workflow.nodes.evaluation_node import evaluation_node
from src.workflow.nodes.validation_node import content_validation_node
from src.utils.clean_logger import CleanLogger
from src.workflow.models import SimpleStorageApprovalRequest


def create_advanced_processing_workflow():
    """
    Create workflow with CONTENT VALIDATION + INTELLIGENT EVALUATION
    
    NEW: Added content_validation node after extraction
    
    Flow:
    1. Extract (with file format validation)
    2. Validate Content (LLM checks if it's a product demo)
    3. Analyze (existing)
    4. Evaluate Analysis (existing)
    5. Suggest Graphs (existing)
    6. Evaluate Graphs (existing)
    7. Chunk (existing)
    8. END (storage handled separately via API endpoint)
    """
    workflow = StateGraph(ProcessingState)
    logger = CleanLogger("workflow.graph")
    
    logger.workflow_start("Creating advanced processing workflow", "with content validation and intelligent evaluation")
    
    # Add all nodes (storage removed - handled separately)
    workflow.add_node("extract", extraction_node)
    workflow.add_node("validate_content", content_validation_node)  # NEW
    workflow.add_node("analyze", analysis_node)
    workflow.add_node("evaluate_analysis", evaluation_node)
    workflow.add_node("suggest_graphs", graph_suggestion_node)
    workflow.add_node("evaluate_graphs", evaluation_node)
    workflow.add_node("chunk", chunking_node)
    workflow.add_node("handle_errors", error_node)
    
    # Set entry point
    workflow.set_entry_point("extract")
    
    logger.workflow_success("Workflow nodes added", "8 nodes configured")
    
    # ============================================
    # ROUTERS WITH NEW VALIDATION LOGIC
    # ============================================
    
    def route_after_extract(state: ProcessingState) -> str:
        """
        After extraction, check for errors then validate content
        
        NEW: Routes to content validation instead of directly to analysis
        """
        if state.get("errors") and not state.get("extracted_markdown"):
            logger.workflow_error("extraction", "Extraction failed critically")
            return "handle_errors"
        
        # Check file validation results (if available)
        file_validation = state.get("file_validation", {})
        if file_validation and not file_validation.get("is_valid", True):
            logger.validation_error("file_format", "File format validation failed")
            return "handle_errors"
        
        logger.log_route("extract", "validate_content", "Content validation required")
        return "validate_content"
    
    def route_after_content_validation(state: ProcessingState) -> str:
        """
        NEW ROUTER: After content validation, proceed to analysis or error
        
        Checks if content is a valid product demo
        """
        is_valid = state.get("is_valid_content", False)
        validation_result = state.get("content_validation", {})
        
        if not is_valid:
            confidence = validation_result.get("confidence", 0.0)
            content_type = validation_result.get("content_type", "unknown")
            logger.validation_error("content", f"Content validation failed: {content_type} (confidence: {confidence:.2f})")
            logger.info(f"Validation feedback: {validation_result.get('feedback', 'No feedback')}")
            return "handle_errors"
        
        logger.log_route("validate_content", "analyze", "Content validated as product demo")
        return "analyze"
    
    def route_after_analysis(state: ProcessingState) -> str:
        """After analysis, check for errors then proceed to evaluation"""
        if state.get("errors") and not state.get("analysis_result"):
            logger.workflow_error("analysis", "Analysis failed critically")
            return "handle_errors"
        logger.log_route("analyze", "evaluate_analysis", "Analysis completed successfully")
        return "evaluate_analysis"
    
    def route_after_analysis_evaluation(state: ProcessingState) -> str:
        """
        INTELLIGENT ROUTING based on evaluation results
        """
        needs_reanalysis = state.get("needs_reanalysis", False)
        evaluation = state.get("output_evaluation", {})
        attempts = state.get("evaluation_attempts", 0)
        
        # Handle list returns from LLM
        if isinstance(evaluation, list):
            evaluation = evaluation[0] if evaluation else {}
        
        issue_type = evaluation.get("issue_type", "no_issue")
        confidence = evaluation.get("confidence", 0.5)
        
        # INTELLIGENT DECISION LOGIC
        if needs_reanalysis and attempts < 2:
            logger.log_retry("analysis", attempts + 1, 2, f"Quality low (confidence: {confidence:.2f})")
            return "analyze"
        
        if issue_type == "source_limitation":
            logger.log_route("evaluate_analysis", "suggest_graphs", "Source limitations identified (expected)")
            return "suggest_graphs"
        
        if confidence < 0.3 and attempts < 2:
            logger.log_retry("analysis", attempts + 1, 2, f"Very low confidence ({confidence:.2f})")
            state["needs_reanalysis"] = True
            return "analyze"
        
        # Default: proceed to next step
        logger.log_route("evaluate_analysis", "suggest_graphs", f"Analysis acceptable (confidence: {confidence:.2f})")
        return "suggest_graphs"
    
    def route_after_graph_suggestion(state: ProcessingState) -> str:
        """After graph generation, always evaluate graphs"""
        if state.get("errors") and not state.get("graph_suggestions"):
            logger.workflow_error("graph_generation", "Graph generation failed critically")
            return "handle_errors"
        logger.log_route("suggest_graphs", "evaluate_graphs", "Graph generation completed successfully")
        return "evaluate_graphs"
    
    def route_after_graph_evaluation(state: ProcessingState) -> str:
        """
        INTELLIGENT ROUTING based on graph evaluation
        """
        needs_regraph = state.get("needs_regraph", False)
        evaluation = state.get("output_evaluation", {})
        attempts = state.get("evaluation_attempts", 0)
        
        # Handle list returns
        if isinstance(evaluation, list):
            evaluation = evaluation[0] if evaluation else {}
        
        issue_type = evaluation.get("issue_type", "no_issue")
        confidence = evaluation.get("confidence", 0.5)
        
        # INTELLIGENT DECISION LOGIC
        if needs_regraph and attempts < 2:
            logger.log_retry("graph_generation", attempts + 1, 2, f"Quality low (confidence: {confidence:.2f})")
            return "suggest_graphs"
        
        if issue_type == "graph_issue" and confidence < 0.5 and attempts < 2:
            logger.log_retry("graph_generation", attempts + 1, 2, f"Graph issues detected (confidence: {confidence:.2f})")
            state["needs_regraph"] = True
            return "suggest_graphs"
        
        # Default: proceed to chunking
        logger.log_route("evaluate_graphs", "chunk", f"Graphs acceptable (confidence: {confidence:.2f})")
        return "chunk"
    
    def route_after_chunk(state: ProcessingState) -> str:
        """After chunking, workflow ends - storage handled separately"""
        if not state.get("chunks"):
            logger.workflow_error("chunking", "Chunking produced no chunks")
            return "handle_errors"
        chunk_count = len(state.get('chunks', []))
        logger.log_route("chunk", "END", f"Chunking completed ({chunk_count} chunks) - storage via API")
        return END
    
    # ============================================
    # WORKFLOW EDGES - Updated with Validation
    # ============================================
    
    # Extract → Validate Content (NEW)
    workflow.add_conditional_edges(
        "extract",
        route_after_extract,
        {
            "validate_content": "validate_content",
            "handle_errors": "handle_errors"
        }
    )
    
    # Validate Content → Analyze (NEW)
    workflow.add_conditional_edges(
        "validate_content",
        route_after_content_validation,
        {
            "analyze": "analyze",
            "handle_errors": "handle_errors"
        }
    )
    
    # Analyze → Evaluate Analysis
    workflow.add_conditional_edges(
        "analyze",
        route_after_analysis,
        {
            "evaluate_analysis": "evaluate_analysis",
            "handle_errors": "handle_errors"
        }
    )
    
    # Evaluate Analysis → Suggest Graphs OR Retry Analysis
    workflow.add_conditional_edges(
        "evaluate_analysis",
        route_after_analysis_evaluation,
        {
            "suggest_graphs": "suggest_graphs",
            "analyze": "analyze",
            "handle_errors": "handle_errors"
        }
    )
    
    # Suggest Graphs → Evaluate Graphs
    workflow.add_conditional_edges(
        "suggest_graphs",
        route_after_graph_suggestion,
        {
            "evaluate_graphs": "evaluate_graphs",
            "handle_errors": "handle_errors"
        }
    )
    
    # Evaluate Graphs → Chunk OR Retry Graphs
    workflow.add_conditional_edges(
        "evaluate_graphs",
        route_after_graph_evaluation,
        {
            "chunk": "chunk",
            "suggest_graphs": "suggest_graphs",
            "handle_errors": "handle_errors"
        }
    )
    
    # Chunk → END (storage handled separately)
    workflow.add_conditional_edges(
        "chunk",
        route_after_chunk,
        {
            END: END,
            "handle_errors": "handle_errors"
        }
    )
    
    # Handle errors always ends
    workflow.add_edge("handle_errors", END)
    
    logger.workflow_success("Workflow compilation", "All edges and routes configured")
    return workflow.compile()

# Create workflow instance
processing_workflow = create_advanced_processing_workflow()