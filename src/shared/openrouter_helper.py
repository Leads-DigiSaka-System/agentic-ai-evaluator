from typing import Optional, List, Dict, Any
from openai import OpenAI
from src.shared.logging.clean_logger import get_clean_logger
from src.shared.llm_helper import get_langfuse_handler
import os

logger = get_clean_logger(__name__)

# Import ChatOpenAI from langchain_community (standard, reliable)
from langchain_community.chat_models import ChatOpenAI


def get_openrouter_client() -> Optional[OpenAI]:
    """
    Get OpenRouter OpenAI client instance.
    
    Returns:
        OpenAI client configured for OpenRouter, or None if API key not configured
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not configured in environment")
        return None
    
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        logger.debug("OpenRouter client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize OpenRouter client: {str(e)}")
        return None


def create_openrouter_llm(
    model: str = "meta-llama/llama-3.3-70b-instruct:free",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    callbacks: Optional[List] = None
) -> Optional[ChatOpenAI]:
    """
    Create LangChain ChatOpenAI instance configured for OpenRouter.
    
    Args:
        model: Model identifier (default: meta-llama/llama-3.3-70b-instruct:free)
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens to generate (None for no limit)
        callbacks: LangChain callbacks for tracking
    
    Returns:
        ChatOpenAI instance configured for OpenRouter, or None if configuration fails
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not configured. Check OPENROUTER_API_KEY in .env file")
        return None
    
    # CRITICAL: Set environment variable as fallback
    # LangChain often checks OPENAI_API_KEY from environment first
    # This ensures Deep Agents can find the API key when it invokes the LLM
    os.environ['OPENAI_API_KEY'] = api_key
    logger.debug("Set OPENAI_API_KEY environment variable for LangChain compatibility")
    
    try:
        # Create ChatOpenAI with OpenRouter configuration
        # OpenRouter is OpenAI-compatible, so we can use ChatOpenAI
        # Try different parameter combinations to ensure API key is set correctly
        
        # CRITICAL: Disable streaming for tool-based agents
        # Tools are not supported in streaming mode
        streaming = False
        
        # Method 1: Try with api_key parameter (newer langchain versions)
        try:
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,  # Try api_key first
                base_url="https://openrouter.ai/api/v1",
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,  # Disable streaming for tools
                callbacks=callbacks,
            )
            logger.debug("Using api_key parameter (newer format)")
        except (TypeError, ValueError) as e1:
            logger.debug(f"api_key parameter failed: {str(e1)}, trying openai_api_key...")
            # Method 2: Try with openai_api_key parameter (older/langchain_openai)
            try:
                llm = ChatOpenAI(
                    model=model,
                    openai_api_key=api_key,  # Try openai_api_key
                    base_url="https://openrouter.ai/api/v1",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,  # Disable streaming for tools
                    callbacks=callbacks,
                )
                logger.debug("Using openai_api_key parameter")
            except (TypeError, ValueError) as e2:
                logger.debug(f"openai_api_key parameter failed: {str(e2)}, trying model_name...")
                # Method 3: Try with model_name and openai_api_base (langchain_community)
                try:
                    llm = ChatOpenAI(
                        model_name=model,
                        openai_api_key=api_key,
                        openai_api_base="https://openrouter.ai/api/v1",
                        temperature=temperature,
                        max_tokens=max_tokens,
                        streaming=streaming,  # Disable streaming for tools
                        callbacks=callbacks,
                    )
                    logger.debug("Using model_name and openai_api_base parameters")
                except Exception as e3:
                    logger.error(f"All parameter combinations failed: {str(e3)}")
                    raise ValueError(f"Failed to create ChatOpenAI with any parameter combination. Last error: {str(e3)}") from e3
        
        # Verify and ensure API key is set on the LLM object
        # Some LangChain versions need the key set as an attribute
        if hasattr(llm, 'openai_api_key'):
            if not llm.openai_api_key or llm.openai_api_key != api_key:
                llm.openai_api_key = api_key
                logger.debug("Set openai_api_key attribute on LLM object")
        if hasattr(llm, 'api_key'):
            if not llm.api_key or llm.api_key != api_key:
                llm.api_key = api_key
                logger.debug("Set api_key attribute on LLM object")
        
        # Note: Don't modify llm.client directly
        # LangChain's ChatOpenAI manages its own client internally
        # The API key is already set via the constructor parameters above
        
        logger.info(f"✅ OpenRouter LLM configured: {model} (API key set via parameter, environment, and client)")
        
        return llm
        
    except Exception as e:
        logger.error(f"Failed to create OpenRouter LLM: {str(e)}")
        return None


def invoke_openrouter_direct(
    messages: List[Dict[str, str]],
    model: str = "meta-llama/llama-3.3-70b-instruct:free",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> Optional[str]:
    """
    Direct invocation of OpenRouter API (without LangChain).
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model identifier
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
    
    Returns:
        Response content string, or None if error
    """
    client = get_openrouter_client()
    if not client:
        return None
    
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        if completion.choices and len(completion.choices) > 0:
            return completion.choices[0].message.content
        else:
            logger.warning("OpenRouter returned empty completion")
            return None
            
    except Exception as e:
        logger.error(f"OpenRouter API call failed: {str(e)}")
        return None


def get_openrouter_model_info(model: str = "meta-llama/llama-3.3-70b-instruct:free") -> Dict[str, Any]:
    """
    Get information about an OpenRouter model.
    
    Args:
        model: Model identifier
    
    Returns:
        Dictionary with model information
    """
    return {
        "model": model,
        "provider": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "free": model.endswith(":free"),
        "context_length": 131072,  # Llama 3.3 70B has 131k context
        "supports_streaming": True,
        "supports_function_calling": True,
        "multilingual": True,
        "supported_languages": [
            "English", "German", "French", "Italian", 
            "Portuguese", "Hindi", "Spanish", "Thai"
        ]
    }


def is_openrouter_configured() -> bool:
    """
    Check if OpenRouter is properly configured.
    
    Returns:
        True if OPENROUTER_API_KEY is set, False otherwise
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    return bool(api_key and api_key.strip())

