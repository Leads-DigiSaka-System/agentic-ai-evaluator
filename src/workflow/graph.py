from langgraph.graph import StateGraph, END
from src.workflow.state import ProcessingState
from src.workflow.nodes.nodes import extraction_node, analysis_node, chunking_node, storage_node, error_node
from src.workflow.nodes.graph_suggestion_node import graph_suggestion_node
from src.Agents.goal_reasoner import goal_reasoner
from src.workflow.nodes.evaluation_node import evaluation_node  # ADD THIS IMPORT

def create_advanced_processing_workflow():
    """Create advanced workflow with goal reasoning and evaluation"""
    workflow = StateGraph(ProcessingState)
    
    # Add all nodes INCLUDING evaluation node
    workflow.add_node("extract", extraction_node)
    workflow.add_node("analyze", analysis_node)
    workflow.add_node("suggest_graphs", graph_suggestion_node)
    workflow.add_node("evaluate", evaluation_node)  # ADD THIS NODE
    workflow.add_node("chunk", chunking_node)
    workflow.add_node("store", storage_node)
    workflow.add_node("handle_errors", error_node)
    
    # Set entry point
    workflow.set_entry_point("extract")
    
    def dynamic_router(state: ProcessingState) -> str:
        """Use goal reasoner to dynamically route to next step"""
        try:
            # Get next action from goal reasoner
            reasoner_result = goal_reasoner(state)
            next_action = reasoner_result.get("next_action", "handle_errors")
            reason = reasoner_result.get("reason", "No reason provided")
            
            print(f"🎯 Goal Reasoner: {next_action} - {reason}")
            
            # Map actions to nodes - INCLUDING EVALUATE
            action_to_node = {
                "extract": "extract",
                "analyze": "analyze", 
                "suggest_graphs": "suggest_graphs",
                "evaluate": "evaluate",  # ADD THIS MAPPING
                "store": "store",
                "retry": "handle_errors"
            }
            
            return action_to_node.get(next_action, "handle_errors")
            
        except Exception as e:
            print(f"❌ Goal reasoner failed: {str(e)}")
            return "handle_errors"
    
    # Use goal reasoner for ALL transitions
    workflow.add_conditional_edges(
        "extract",
        dynamic_router,
        {
            "analyze": "analyze",
            "suggest_graphs": "suggest_graphs", 
            "evaluate": "evaluate",  # ADD THIS
            "store": "store",
            "handle_errors": "handle_errors",
            "extract": "extract"
        }
    )
    
    workflow.add_conditional_edges(
        "analyze",
        dynamic_router,
        {
            "suggest_graphs": "suggest_graphs",
            "evaluate": "evaluate",  # ADD THIS
            "store": "store",
            "handle_errors": "handle_errors",
            "analyze": "analyze",
            "extract": "extract"
        }
    )
    
    workflow.add_conditional_edges(
        "suggest_graphs",
        dynamic_router, 
        {
            "evaluate": "evaluate",  # ADD THIS (most common path)
            "chunk": "chunk",
            "store": "store",
            "handle_errors": "handle_errors",
            "suggest_graphs": "suggest_graphs",
            "analyze": "analyze"
        }
    )
    
    workflow.add_conditional_edges(
        "evaluate",  # ADD THIS NEW NODE'S CONDITIONAL EDGES
        dynamic_router,
        {
            "chunk": "chunk",
            "store": "store", 
            "handle_errors": "handle_errors",
            "analyze": "analyze",  # If evaluation says re-analyze
            "suggest_graphs": "suggest_graphs",  # If need better graphs
            "evaluate": "evaluate"  # For retries
        }
    )
    
    workflow.add_conditional_edges(
        "chunk",
        dynamic_router,
        {
            "store": "store",
            "handle_errors": "handle_errors",
            "chunk": "chunk"
        }
    )
    
    workflow.add_conditional_edges(
        "store",
        dynamic_router,
        {
            "handle_errors": "handle_errors",
            END: END
        }
    )
    
    workflow.add_edge("handle_errors", END)
    
    return workflow.compile()

# Advanced workflow instance
processing_workflow = create_advanced_processing_workflow()