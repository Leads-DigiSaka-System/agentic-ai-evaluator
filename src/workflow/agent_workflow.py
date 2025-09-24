# file: src/graph/workflow.py
from langgraph.graph import StateGraph,END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, Dict, Any, Optional, List
from langchain_core.runnables import RunnableLambda

from src.workflow.node_edges import (
    query_rewriter_step,
    retriever_step,
    synthesizer_step,
    error_handler_step,
    check_retrieval_success_step,
    check_synthesis_success_step,
    check_data_quality_step
)

class GraphState(TypedDict):
    # Input
    query: str
    top_k: int
    
    # Processing steps
    rewritten_query: Optional[str]
    search_results: Optional[List[Dict[str, Any]]]
    retrieved_context: Optional[str]
    chunk_count: Optional[int]
    final_prompt: Optional[str]
    
    # Output
    synthesized_output: Optional[str]
    
    # Error handling
    error: Optional[str]
    error_step: Optional[str]
    decision: Optional[str]

# Initialize graph
graph = StateGraph(GraphState)

# Register nodes
graph.add_node("query_rewriter", RunnableLambda(query_rewriter_step))
graph.add_node("retriever", RunnableLambda(retriever_step))
graph.add_node("check_data_quality", RunnableLambda(check_data_quality_step))
graph.add_node("check_retrieval_success", RunnableLambda(check_retrieval_success_step))
graph.add_node("synthesizer", RunnableLambda(synthesizer_step))
graph.add_node("check_synthesis_success", RunnableLambda(check_synthesis_success_step))
graph.add_node("error_handler", RunnableLambda(error_handler_step))

# Entry point
graph.set_entry_point("query_rewriter")

# Main flow: query rewrite -> retrieve -> check data quality
graph.add_edge("query_rewriter", "retriever")
graph.add_edge("retriever", "check_data_quality")

# Conditional path for data quality
graph.add_conditional_edges(
    "check_data_quality",
    lambda state: state.get("decision"),
    path_map={
        "proceed": "check_retrieval_success",
        "abort": "error_handler"
    }
)

# Conditional path for retrieval success
graph.add_conditional_edges(
    "check_retrieval_success",
    lambda state: state.get("decision"),
    path_map={
        "continue": "synthesizer",
        "error": "error_handler"
    }
)

# After synthesis, check if it was successful
graph.add_edge("synthesizer", "check_synthesis_success")

# Conditional path for synthesis success
graph.add_conditional_edges(
    "check_synthesis_success",
    lambda state: state.get("decision"),
    path_map={
        "continue": END,
        "error": "error_handler"
    }
)

# Error handler goes to end
graph.add_edge("error_handler", END)

# Compile with memory
memory = MemorySaver()
rag_graph = graph.compile(checkpointer=memory)