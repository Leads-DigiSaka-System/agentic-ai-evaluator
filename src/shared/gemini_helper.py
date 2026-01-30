"""
Gemini LLM Helper for Chat Agent

Provides ChatGoogleGenerativeAI instance configured for LangChain agents.
Similar structure to openrouter_helper.py for consistency.
"""
from typing import Optional, List
from langchain_google_genai import ChatGoogleGenerativeAI
from src.core.config import GOOGLE_API_KEY, GEMINI_MODEL
from src.shared.logging.clean_logger import get_clean_logger
from src.shared.llm_helper import get_langfuse_handler
import os

logger = get_clean_logger(__name__)


def is_gemini_configured() -> bool:
    """
    Check if Gemini is properly configured.
    
    Returns:
        True if GEMINI_APIKEY is set, False otherwise
    """
    api_key = os.getenv("GEMINI_APIKEY") or GOOGLE_API_KEY
    return bool(api_key and api_key.strip())


def create_gemini_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    callbacks: Optional[List] = None
) -> Optional[ChatGoogleGenerativeAI]:
    """
    Create LangChain ChatGoogleGenerativeAI instance for agents.
    
    Args:
        model: Model identifier (default: GEMINI_MODEL from config)
               Examples: "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens to generate (None for model default)
                    Note: Internally converted to max_output_tokens for Gemini
        callbacks: LangChain callbacks for tracking
    
    Returns:
        ChatGoogleGenerativeAI instance, or None if configuration fails
    """
    api_key = os.getenv("GEMINI_APIKEY") or GOOGLE_API_KEY
    if not api_key:
        logger.error("GEMINI_APIKEY is not configured. Check GEMINI_APIKEY in .env file")
        return None
    
    model_name = model or GEMINI_MODEL
    if not model_name:
        logger.error("GEMINI_MODEL is not configured. Check GEMINI_MODEL in .env file")
        return None
    
    try:
        # Create ChatGoogleGenerativeAI with Gemini configuration
        # Note: Gemini uses max_output_tokens instead of max_tokens
        llm_kwargs = {
            "model": model_name,
            "google_api_key": api_key,
            "temperature": temperature,
            "callbacks": callbacks,
        }
        
        # Only add max_output_tokens if max_tokens is provided
        if max_tokens is not None:
            llm_kwargs["max_output_tokens"] = max_tokens
        
        llm = ChatGoogleGenerativeAI(**llm_kwargs)
        
        logger.info(f"✅ Gemini LLM configured: {model_name}")
        return llm
        
    except Exception as e:
        logger.error(f"Failed to create Gemini LLM: {str(e)}")
        return None


def get_gemini_model_info(model: str = None) -> dict:
    """
    Get information about a Gemini model.
    
    Args:
        model: Model identifier (default: GEMINI_MODEL from config)
    
    Returns:
        Dictionary with model information
    """
    model_name = model or GEMINI_MODEL or "gemini-1.5-flash"
    
    # Model context lengths (approximate)
    context_lengths = {
        "gemini-1.5-flash": 1000000,  # 1M tokens
        "gemini-1.5-pro": 2000000,     # 2M tokens
        "gemini-2.0-flash-exp": 1000000,
    }
    
    return {
        "model": model_name,
        "provider": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "context_length": context_lengths.get(model_name, 1000000),
        "supports_streaming": True,
        "supports_function_calling": True,
        "multilingual": True,
        "supported_languages": [
            "English", "Spanish", "French", "German", "Italian",
            "Portuguese", "Chinese", "Japanese", "Korean", "Hindi"
        ]
    }

