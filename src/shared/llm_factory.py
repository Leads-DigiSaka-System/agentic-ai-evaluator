"""
LLM Factory for creating LLM instances based on provider

Provides a unified interface for creating LLM instances for chat agents,
supporting both OpenRouter and Gemini providers.
"""
from typing import Optional, List
from langchain_core.language_models import BaseChatModel
from src.shared.openrouter_helper import create_openrouter_llm, is_openrouter_configured
from src.shared.gemini_helper import create_gemini_llm, is_gemini_configured
from src.shared.llm_helper import get_langfuse_handler
from src.core.config import OPENROUTER_MODEL, GEMINI_MODEL
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def create_llm_for_agent(
    provider: str = "openrouter",
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> Optional[BaseChatModel]:
    """
    Factory function to create LLM instance for agent based on provider.
    
    Args:
        provider: "openrouter" or "gemini" (case-insensitive)
        model: Optional model identifier (overrides default from config)
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens (None for model default)
    
    Returns:
        LLM instance (ChatOpenAI or ChatGoogleGenerativeAI), or None if configuration fails
    
    Raises:
        ValueError: If provider is not supported or not configured
    """
    provider_lower = provider.lower()
    
    # Get callbacks (Langfuse tracking)
    callbacks = []
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler:
        callbacks.append(langfuse_handler)
    
    if provider_lower == "gemini":
        if not is_gemini_configured():
            logger.error("Gemini is not configured. Check GEMINI_APIKEY in .env file")
            raise ValueError("Gemini is not configured. Check GEMINI_APIKEY in .env file")
        
        llm = create_gemini_llm(
            model=model or GEMINI_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks if callbacks else None
        )
        
        if not llm:
            raise ValueError(
                "Failed to create Gemini LLM. "
                "Check GEMINI_APIKEY and GEMINI_MODEL configuration."
            )
        
        logger.info(f"✅ Created Gemini LLM: {model or GEMINI_MODEL}")
        return llm
        
    elif provider_lower == "openrouter":
        if not is_openrouter_configured():
            logger.error("OpenRouter is not configured. Check OPENROUTER_API_KEY in .env file")
            raise ValueError("OpenRouter is not configured. Check OPENROUTER_API_KEY in .env file")
        
        llm = create_openrouter_llm(
            model=model or OPENROUTER_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks if callbacks else None
        )
        
        if not llm:
            raise ValueError(
                "Failed to create OpenRouter LLM. "
                "Check OPENROUTER_API_KEY and OPENROUTER_MODEL configuration."
            )
        
        logger.info(f"✅ Created OpenRouter LLM: {model or OPENROUTER_MODEL}")
        return llm
        
    else:
        raise ValueError(
            f"Unsupported provider: {provider}. "
            "Supported providers: 'openrouter', 'gemini'"
        )


def get_available_providers() -> List[str]:
    """
    Get list of available (configured) LLM providers.
    
    Returns:
        List of provider names that are configured
    """
    providers = []
    if is_openrouter_configured():
        providers.append("openrouter")
    if is_gemini_configured():
        providers.append("gemini")
    return providers

