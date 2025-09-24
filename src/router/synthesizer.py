# file: src/router/synthesizer.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
import uuid
from langchain_core.runnables import RunnableLambda
from src.workflow.agent_workflow import rag_graph

router = APIRouter()

class PipelineRequest(BaseModel):
    query: str
    top_k: int = 5
    thread_id: str = None  # Optional thread ID for conversation continuity

@router.post("/full_pipeline")   
def full_pipeline(request: PipelineRequest) -> Dict[str, Any]:
    """
    Perform search + retrieve + synthesize using LangGraph pipeline.
    """
    # Initialize state
    initial_state = {
        "query": request.query,
        "top_k": request.top_k,
        "rewritten_query": None,
        "search_results": None,
        "retrieved_context": None,
        "chunk_count": None,
        "final_prompt": None,
        "synthesized_output": None,
        "error": None,
        "error_step": None,
        "decision": None
    }
    
    # Generate thread_id if not provided
    thread_id = request.thread_id or str(uuid.uuid4())
    
    # Configuration for checkpointer
    config = {"configurable": {"thread_id": thread_id}}
    
    # Execute the graph with config
    final_state = rag_graph.invoke(initial_state, config=config)
    
    # Prepare response
    response = {
        "synthesized_output": final_state["synthesized_output"],
        "thread_id": thread_id  # Return thread_id for future requests
    }
    
    # Include debug information if needed (optional)
    if final_state.get("error"):
        response["error_info"] = {
            "step": final_state.get("error_step"),
            "message": final_state.get("error")
        }
    
    return response