"""
Retry utility with exponential backoff for LLM API calls

Handles transient failures in LLM API calls with automatic retries.
"""
import time
import random
from typing import Callable, TypeVar, Any, Optional
from functools import wraps
from src.utils.clean_logger import get_clean_logger
from src.utils.config import (
    MAX_RETRY_ATTEMPTS,
    LLM_TIMEOUT_SECONDS,
    LLM_RETRY_BASE_DELAY,
    LLM_RETRY_MAX_DELAY
)

logger = get_clean_logger(__name__)

T = TypeVar('T')


def retry_with_exponential_backoff(
    max_attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    timeout: Optional[float] = None,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: from config)
        base_delay: Base delay in seconds for exponential backoff (default: from config)
        max_delay: Maximum delay in seconds (default: from config)
        timeout: Timeout in seconds for each attempt (default: from config)
        retryable_exceptions: Tuple of exceptions that should trigger retry
    
    Returns:
        Decorated function with retry logic
    """
    max_attempts = max_attempts or MAX_RETRY_ATTEMPTS
    base_delay = base_delay or LLM_RETRY_BASE_DELAY
    max_delay = max_delay or LLM_RETRY_MAX_DELAY
    timeout = timeout or LLM_TIMEOUT_SECONDS
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Call the function
                    result = func(*args, **kwargs)
                    
                    # If successful, return result
                    if attempt > 1:
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempt}")
                    return result
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Don't retry on last attempt
                    if attempt >= max_attempts:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts: {str(e)}"
                        )
                        raise
                    
                    # Calculate exponential backoff delay with jitter
                    # Formula: base_delay * (2 ^ (attempt - 1)) + random_jitter
                    delay = min(
                        base_delay * (2 ** (attempt - 1)),
                        max_delay
                    )
                    # Add jitter (random 0-25% of delay) to prevent thundering herd
                    jitter = random.uniform(0, delay * 0.25)
                    total_delay = delay + jitter
                    
                    error_msg = str(e)
                    error_type = type(e).__name__
                    
                    logger.warning(
                        f"⚠️ {func.__name__} failed on attempt {attempt}/{max_attempts} "
                        f"({error_type}): {error_msg[:100]}... "
                        f"Retrying in {total_delay:.2f}s..."
                    )
                    
                    # Wait before retrying
                    time.sleep(total_delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed after {max_attempts} attempts")
        
        return wrapper
    return decorator


def retry_llm_call(
    func: Callable[..., T],
    *args,
    max_attempts: Optional[int] = None,
    **kwargs
) -> T:
    """
    Retry an LLM call with exponential backoff.
    
    Convenience function for retrying LLM calls without decorator syntax.
    
    Args:
        func: Function to retry (usually LLM invoke)
        *args: Positional arguments for func
        max_attempts: Maximum retry attempts (default: from config)
        **kwargs: Keyword arguments for func
    
    Returns:
        Result from func
    
    Raises:
        Last exception if all retries fail
    """
    max_attempts = max_attempts or MAX_RETRY_ATTEMPTS
    base_delay = LLM_RETRY_BASE_DELAY
    max_delay = LLM_RETRY_MAX_DELAY
    
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            result = func(*args, **kwargs)
            if attempt > 1:
                logger.info(f"✅ LLM call succeeded on attempt {attempt}")
            return result
            
        except Exception as e:
            last_exception = e
            
            if attempt >= max_attempts:
                logger.error(
                    f"❌ LLM call failed after {max_attempts} attempts: {str(e)}"
                )
                raise
            
            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, delay * 0.25)
            total_delay = delay + jitter
            
            logger.warning(
                f"⚠️ LLM call failed on attempt {attempt}/{max_attempts} "
                f"({type(e).__name__}): {str(e)[:100]}... "
                f"Retrying in {total_delay:.2f}s..."
            )
            
            time.sleep(total_delay)
    
    if last_exception:
        raise last_exception
    raise RuntimeError(f"LLM call failed after {max_attempts} attempts")

