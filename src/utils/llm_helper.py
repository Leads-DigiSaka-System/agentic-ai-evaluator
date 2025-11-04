from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.config import GOOGLE_API_KEY, GEMINI_MODEL
from src.formatter.json_helper import clean_json_from_llm_response
from src.utils.clean_logger import get_clean_logger
from typing import Optional, Dict, Any

# Shared Gemini instance (singleton)
llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,
)

def invoke_llm(
    prompt: str,
    as_json: bool = False,
    trace_id: Optional[str] = None,
    generation_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
    """
    Send a prompt to Gemini and return the response with optional Langfuse tracing.

    Args:
        prompt (str): Prompt string to send
        as_json (bool): If True, tries to clean and return parsed JSON
        trace_id (str, optional): Langfuse trace ID for observability
        generation_name (str, optional): Name for this LLM generation in Langfuse
            (e.g., "analysis", "validation", "graph_suggestion")
        metadata (dict, optional): Additional metadata for Langfuse tracking

    Returns:
        str or dict: Raw string response or parsed dict, or None on error
    """
    logger = get_clean_logger(__name__)

    try:
        logger.llm_request(GEMINI_MODEL, "text generation" if not as_json else "json generation")
        
        # Get Langfuse callback handler if trace_id provided
        callbacks = []
        config = {}
        if trace_id:
            from src.utils.langfuse_helper import get_langfuse_handler
            from langchain_core.runnables import RunnableConfig
            
            handler = get_langfuse_handler(trace_id=trace_id)
            if handler:
                callbacks = [handler]
                
                # Pass trace context through LangChain config
                # CallbackHandler needs trace_id in metadata to link to existing trace
                # Langfuse CallbackHandler reads trace_id from OpenTelemetry context or metadata
                config_metadata = {
                    "trace_id": trace_id,
                    "generation_name": generation_name or "llm_invocation"
                }
                if metadata:
                    config_metadata.update(metadata)
                
                config = RunnableConfig(
                    callbacks=callbacks,
                    tags=[f"trace_id:{trace_id}", f"generation:{generation_name or 'llm_invocation'}"],
                    run_name=generation_name or "llm_invocation",
                    metadata=config_metadata  # Pass trace_id in metadata
                )
        
        # Invoke LLM with callbacks for automatic tracing
        if config:
            response = llm.invoke(prompt, config=config)
        else:
            response = llm.invoke(prompt)
        
        result_text = response.content if hasattr(response, "content") else str(response)
        
        # Note: LangChain callbacks should automatically log to Langfuse
        # If token usage not captured, we can add manual logging here if needed

        if as_json:
            logger.llm_response(GEMINI_MODEL, "json parsed", "success")
            return clean_json_from_llm_response(result_text)

        logger.llm_response(GEMINI_MODEL, "text generated", "success")
        return result_text
    except Exception as e:
        logger.llm_error(GEMINI_MODEL, str(e))
        return None
