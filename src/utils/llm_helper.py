from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.config import GOOGLE_API_KEY, GEMINI_MODEL, LANGFUSE_CONFIGURED, GEMINI_LARGE
from src.formatter.json_helper import clean_json_from_llm_response
from src.utils.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)

# Initialize Langfuse callback handler if configured (v3 API)
_langfuse_handler = None

def get_langfuse_handler():
    """Get or create Langfuse callback handler singleton (v3 API)"""
    global _langfuse_handler
    
    if not LANGFUSE_CONFIGURED:
        return None
    
    if _langfuse_handler is None:
        try:
            # v3 API: Import from langfuse.langchain
            from langfuse.langchain import CallbackHandler
            from src.monitoring.trace.langfuse_helper import initialize_langfuse
            
            # Ensure Langfuse is initialized
            initialize_langfuse()
            
            # Create handler
            _langfuse_handler = CallbackHandler()
            logger.info("✅ Langfuse v3 callback handler initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse handler: {e}")
            _langfuse_handler = None
    
    return _langfuse_handler


# Shared Gemini instance with Langfuse integration
def create_llm():
    """Create LLM instance with Langfuse callback if available (v3 API)"""
    callbacks = []
    handler = get_langfuse_handler()
    
    if handler:
        callbacks.append(handler)
        logger.debug("LLM initialized with Langfuse v3 tracking")
    
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
        callbacks=callbacks if callbacks else None
    )

llm = create_llm()


def invoke_llm(prompt: str, as_json: bool = False, trace_name: str = None):
    """
    Send a prompt to Gemini and return the response with Langfuse tracking (v3).

    Args:
        prompt (str): Prompt string to send
        as_json (bool): If True, tries to clean and return parsed JSON
        trace_name (str): Optional name for the LLM call (for better tracing)

    Returns:
        str or dict: Raw string response or parsed dict
    """
    try:
        # Log request
        operation = "json generation" if as_json else "text generation"
        if trace_name:
            operation = f"{trace_name} ({operation})"
        
        logger.llm_request(GEMINI_MODEL, operation)
        
        # Invoke LLM (Langfuse automatically captures this via callback)
        response = llm.invoke(prompt)
        result_text = response.content if hasattr(response, "content") else str(response)
        
        # Track token usage if available (v3 API)
        if LANGFUSE_CONFIGURED and hasattr(response, 'response_metadata'):
            try:
                from src.monitoring.trace.langfuse_helper import get_langfuse_client
                
                client = get_langfuse_client()
                if not client:
                    logger.debug("Langfuse client not available for token tracking")
                else:
                    metadata = response.response_metadata
                    token_usage = metadata.get('token_usage', {})
                    
                    if token_usage:
                        # v3: Update via current observation with model for cost calculation
                        # Langfuse automatically calculates cost if model name is set
                        try:
                            client.update_current_observation(
                                usage={
                                    "input": token_usage.get('prompt_tokens', 0),
                                    "output": token_usage.get('completion_tokens', 0),
                                    "total": token_usage.get('total_tokens', 0),
                                    "unit": "TOKENS"
                                },
                                model=GEMINI_MODEL  # Set model name for automatic cost calculation
                            )
                            logger.debug(f"Token usage logged: {token_usage.get('total_tokens', 0)} tokens | Model: {GEMINI_MODEL}")
                        except Exception as update_err:
                            logger.debug(f"Could not update observation with tokens: {update_err}")
            except Exception as e:
                logger.debug(f"Could not log token usage: {e}")
        
        # Parse JSON if requested
        if as_json:
            parsed = clean_json_from_llm_response(result_text)
            logger.llm_response(GEMINI_MODEL, "json parsed", "success")
            return parsed
        
        logger.llm_response(GEMINI_MODEL, "text generated", "success")
        return result_text
        
    except Exception as e:
        logger.llm_error(GEMINI_MODEL, str(e))
        
        # Log error to Langfuse if configured (v3 API)
        if LANGFUSE_CONFIGURED:
            try:
                from src.monitoring.trace.langfuse_helper import update_trace_with_error
                update_trace_with_error(e, {"operation": operation, "model": GEMINI_MODEL})
            except Exception as langfuse_err:
                logger.debug(f"Failed to log LLM error to Langfuse: {langfuse_err}")
        
        return None

def large_llm(prompt: str, as_json: bool = False, trace_name: str = None):
    """
        Send a prompt to Gemini and return the response with Langfuse tracking (v3).

    Args:
        prompt (str): Prompt string to send
        as_json (bool): If True, tries to clean and return parsed JSON
        trace_name (str): Optional name for the LLM call (for better tracing)

    Returns:
        str or dict: Raw string response or parsed dict
    """
    try:
        # Log request
        operation = "json generation" if as_json else "text generation"
        if trace_name:
            operation = f"{trace_name} ({operation})"
        
        logger.llm_request(GEMINI_LARGE, operation)
        
        # Invoke LLM (Langfuse automatically captures this via callback)
        response = llm.invoke(prompt)
        result_text = response.content if hasattr(response, "content") else str(response)
        
        # Track token usage if available (v3 API)
        if LANGFUSE_CONFIGURED and hasattr(response, 'response_metadata'):
            try:
                from src.monitoring.trace.langfuse_helper import get_langfuse_client
                
                client = get_langfuse_client()
                if not client:
                    logger.debug("Langfuse client not available for token tracking")
                else:
                    metadata = response.response_metadata
                    token_usage = metadata.get('token_usage', {})
                    
                    if token_usage:
                        # v3: Update via current observation with model for cost calculation
                        # Langfuse automatically calculates cost if model name is set
                        try:
                            client.update_current_observation(
                                usage={
                                    "input": token_usage.get('prompt_tokens', 0),
                                    "output": token_usage.get('completion_tokens', 0),
                                    "total": token_usage.get('total_tokens', 0),
                                    "unit": "TOKENS"
                                },
                                model=GEMINI_LARGE  # Set model name for automatic cost calculation
                            )
                            logger.debug(f"Token usage logged: {token_usage.get('total_tokens', 0)} tokens | Model: {GEMINI_LARGE}")
                        except Exception as update_err:
                            logger.debug(f"Could not update observation with tokens: {update_err}")
            except Exception as e:
                logger.debug(f"Could not log token usage: {e}")
        
        # Parse JSON if requested
        if as_json:
            parsed = clean_json_from_llm_response(result_text)
            logger.llm_response(GEMINI_MODEL, "json parsed", "success")
            return parsed
        
        logger.llm_response(GEMINI_MODEL, "text generated", "success")
        return result_text
        
    except Exception as e:
        logger.llm_error(GEMINI_MODEL, str(e))
        
        # Log error to Langfuse if configured (v3 API)
        if LANGFUSE_CONFIGURED:
            try:
                from src.monitoring.trace.langfuse_helper import update_trace_with_error
                update_trace_with_error(e, {"operation": operation, "model": GEMINI_MODEL})
            except Exception as langfuse_err:
                logger.debug(f"Failed to log LLM error to Langfuse: {langfuse_err}")
        
        return None
