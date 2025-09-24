# file: src/graph/nodes.py
from typing import Dict, Any, Optional, List
from src.database.hybrid_search import create_hybrid_search
from src.utils.prompt_template import synthesizer_template
from src.utils.llm_helper import invoke_llm
from src.utils.prompt_helper import query_rewrite_template
from langchain_core.prompts import PromptTemplate
import logging

logger = logging.getLogger(__name__)

# Initialize components
hybrid_search = create_hybrid_search()

#   QUERY REWRITER
def query_rewriter_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite the query for better retrieval"""
    try:
        query = state["query"]
        logger.info(f"Rewriting query: {query}")
        
        template = query_rewrite_template()
        rewrite_prompt = template.format(original_query=query)
        
        rewritten_query = invoke_llm(rewrite_prompt).strip()
        
        logger.info(f"Rewritten query: {rewritten_query}")
        
        return {
            **state,
            "rewritten_query": rewritten_query,
            "error": None,
            "error_step": None
        }
        
    except Exception as e:
        logger.error(f"Error in query rewriter: {str(e)}")
        return {
            **state,
            "rewritten_query": state["query"],  # Fallback to original
            "error": str(e),
            "error_step": "query_rewriter"
        }

#   RETRIEVER
def retriever_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve relevant documents using hybrid search"""
    try:
        # Use rewritten query if available, otherwise original
        query_to_use = state.get("rewritten_query", state["query"])
        top_k = state["top_k"]
        
        logger.info(f"Retrieving with query: {query_to_use}, top_k: {top_k}")
        
        # Perform hybrid search
        results = hybrid_search.search(query=query_to_use, top_k=top_k)
        
        if not results:
            logger.warning("No results retrieved from hybrid search")
            return {
                **state,
                "search_results": [],
                "retrieved_context": "",
                "chunk_count": 0,
                "error": "No results found for the query",
                "error_step": "retriever"
            }
        
        # Prepare context
        retrieved_context = "\n\n".join([r["content"] for r in results])
        chunk_count = len(results)
        
        logger.info(f"Retrieved {chunk_count} chunks")
        
        return {
            **state,
            "search_results": results,
            "retrieved_context": retrieved_context,
            "chunk_count": chunk_count,
            "error": None,
            "error_step": None
        }
        
    except Exception as e:
        logger.error(f"Error in retriever: {str(e)}")
        return {
            **state,
            "search_results": [],
            "retrieved_context": "",
            "chunk_count": 0,
            "error": str(e),
            "error_step": "retriever"
        }

#   SYNTHESIZER
def synthesizer_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesize the final answer using LLM"""
    try:
        retrieved_context = state.get("retrieved_context", "")
        
        if not retrieved_context:
            logger.warning("No context available for synthesis")
            return {
                **state,
                "synthesized_output": "I couldn't find enough information to answer your question.",
                "error": "No context available",
                "error_step": "synthesizer"
            }
        
        # Build synthesizer prompt
        template = synthesizer_template()
        final_prompt = template.format(
            retrieved_context=retrieved_context,
            user_query=state["query"],  # Use original query for synthesis
            chunk_count=state["chunk_count"]
        )
        
        logger.info("Calling LLM for synthesis")
        
        # Call LLM
        llm_response = invoke_llm(final_prompt)
        
        logger.info("Synthesis completed successfully")
        
        return {
            **state,
            "final_prompt": final_prompt,
            "synthesized_output": llm_response,
            "error": None,
            "error_step": None
        }
        
    except Exception as e:
        logger.error(f"Error in synthesizer: {str(e)}")
        return {
            **state,
            "synthesized_output": "I encountered an error while generating the response.",
            "error": str(e),
            "error_step": "synthesizer"
        }

#   ERROR HANDLER
def error_handler_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle errors gracefully and provide fallback responses"""
    error_step = state.get("error_step", "unknown")
    error_msg = state.get("error", "Unknown error")
    
    logger.error(f"Error in step {error_step}: {error_msg}")
    
    # Create appropriate error response based on the failure point
    if error_step == "retriever":
        fallback_response = "I couldn't find relevant information to answer your question. Please try rephrasing your query."
    elif error_step == "synthesizer":
        # If we have context but synthesis failed, provide a basic response
        if state.get("retrieved_context"):
            fallback_response = "Based on the available information, I can provide a summary: " + \
                              state["retrieved_context"][:500] + "..."
        else:
            fallback_response = "I found some information but couldn't process it properly. Please try again."
    else:
        fallback_response = "I encountered an issue while processing your request. Please try again."
    
    return {
        **state,
        "synthesized_output": fallback_response,
        "error": error_msg,
        "error_step": error_step
    }

#   LOGIC EDGES - CHECK RETRIEVAL SUCCESS
def check_retrieval_success_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check if retrieval was successful"""
    error = state.get("error")
    error_step = state.get("error_step")
    
    if error_step == "retriever":
        decision = "error"
    else:
        decision = "continue"
    
    return {**state, "decision": decision}

#   LOGIC EDGES - CHECK SYNTHESIS SUCCESS  
def check_synthesis_success_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check if synthesis was successful"""
    error = state.get("error")
    error_step = state.get("error_step")
    
    if error_step == "synthesizer":
        decision = "error"
    else:
        decision = "continue"
    
    return {**state, "decision": decision}

#   LOGIC EDGES - CHECK DATA QUALITY (for retrieval)
def check_data_quality_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check if we have valid data to proceed"""
    search_results = state.get("search_results", [])
    chunk_count = state.get("chunk_count", 0)
    
    decision = "proceed" if search_results and chunk_count > 0 else "abort"
    return {**state, "decision": decision}