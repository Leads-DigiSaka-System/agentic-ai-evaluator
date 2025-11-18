from langgraph.graph import StateGraph, END
from src.workflow.state import ProcessingState
from src.workflow.nodes.nodes import extraction_node, analysis_node, chunking_node, error_node
from src.workflow.nodes.graph_suggestion_node import graph_suggestion_node
from src.workflow.nodes.evaluation_node import evaluation_node
from src.workflow.nodes.validation_node import content_validation_node
from src.workflow.routers import (
    route_after_extract,
    route_after_content_validation,
    route_after_analysis,
    route_after_analysis_evaluation,
    route_after_graph_suggestion,
    route_after_graph_evaluation,
    route_after_chunk
)
from src.utils.clean_logger import CleanLogger


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