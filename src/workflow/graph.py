from langgraph.graph import StateGraph, END
from src.workflow.state import ProcessingState
from src.workflow.nodes.nodes import extraction_node, analysis_node, chunking_node, storage_node, error_node

def create_advanced_processing_workflow():
    """Create advanced workflow with better error handling"""
    workflow = StateGraph(ProcessingState)
    
    # Add nodes
    workflow.add_node("extract", extraction_node)
    workflow.add_node("analyze", analysis_node)
    workflow.add_node("chunk", chunking_node)
    workflow.add_node("store", storage_node)
    workflow.add_node("handle_errors", error_node)
    
    # Define the flow with conditional edges
    workflow.set_entry_point("extract")
    
    def should_continue_after_extract(state: ProcessingState) -> str:
        """Determine next step based on extraction state"""
        if state.get("errors"):
            return "handle_errors"
        elif not state.get("extracted_markdown"):
            state["errors"].append("No content extracted from PDF")
            return "handle_errors"
        else:
            return "analyze"
    
    workflow.add_conditional_edges(
        "extract",
        should_continue_after_extract,
        {
            "analyze": "analyze",
            "handle_errors": "handle_errors"
        }
    )
    
    def should_continue_after_analysis(state: ProcessingState) -> str:
        """Check state after analysis"""
        if state.get("errors"):
            return "handle_errors"
        elif not state.get("analysis_result"):
            state["errors"].append("No analysis result generated")
            return "handle_errors"
        else:
            return "chunk"
    
    workflow.add_conditional_edges(
        "analyze",
        should_continue_after_analysis,
        {
            "chunk": "chunk",
            "handle_errors": "handle_errors"
        }
    )
    
    def should_continue_after_chunk(state: ProcessingState) -> str:
        """Determine next step after chunking"""
        if state.get("errors"):
            return "handle_errors"
        elif not state.get("chunks"):
            state["errors"].append("No chunks created from content")
            return "handle_errors"
        else:
            return "store"
    
    workflow.add_conditional_edges(
        "chunk",
        should_continue_after_chunk,
        {
            "store": "store",
            "handle_errors": "handle_errors"
        }
    )
    
    def should_continue_after_store(state: ProcessingState) -> str:
        """Determine if storage was successful"""
        if state.get("errors"):
            return "handle_errors"
        else:
            return END
    
    workflow.add_conditional_edges(
        "store",
        should_continue_after_store,
        {
            "handle_errors": "handle_errors",
            END: END
        }
    )
    
    workflow.add_edge("handle_errors", END)
    
    return workflow.compile()

# Advanced workflow instance
processing_workflow = create_advanced_processing_workflow()