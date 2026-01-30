"""
Unified Langfuse utilities module.

This module provides a single import point for all Langfuse functionality,
eliminating repetitive conditional imports across the codebase.
"""
from src.core.config import LANGFUSE_CONFIGURED
from typing import Dict, Any, Optional, Callable, TypeVar, ParamSpec
from functools import wraps
import inspect

# Type variables for decorators
P = ParamSpec('P')
T = TypeVar('T')

# ============================================================================
# Langfuse Availability Check
# ============================================================================

LANGFUSE_AVAILABLE = False
_observe_decorator = None
_get_client_func = None

if LANGFUSE_CONFIGURED:
    try:
        from langfuse import observe, get_client
        LANGFUSE_AVAILABLE = True
        _observe_decorator = observe
        _get_client_func = get_client
    except ImportError:
        LANGFUSE_AVAILABLE = False


# ============================================================================
# Safe Langfuse Operations (Always Available)
# ============================================================================

def safe_observe(*args, **kwargs):
    """
    Safe observe decorator that works whether Langfuse is available or not.
    
    Usage:
        @safe_observe(name="my_function")
        def my_function():
            ...
    """
    if not LANGFUSE_AVAILABLE:
        # Return no-op decorator
        def noop_decorator(func):
            return func
        return noop_decorator
    
    # Use real Langfuse observe decorator
    return _observe_decorator(*args, **kwargs)


def safe_get_client():
    """
    Safely get Langfuse client, returns None if not available.
    
    Returns:
        Langfuse client instance or None
    """
    if not LANGFUSE_AVAILABLE:
        return None
    try:
        return _get_client_func()
    except Exception:
        return None


def safe_update_observation(metadata: Dict[str, Any] = None) -> bool:
    """
    Safely update current observation with metadata.
    Returns True if successful, False otherwise.
    
    Args:
        metadata: Dictionary of metadata to add to current observation
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not LANGFUSE_CONFIGURED or not metadata:
        return False
    
    try:
        client = safe_get_client()
        if client:
            client.update_current_observation(metadata=metadata)
            return True
    except Exception:
        # Silently fail - this is expected if not in observation context
        pass
    
    return False


def safe_update_trace(metadata: Dict[str, Any] = None, **kwargs) -> bool:
    """
    Safely update current trace with metadata or other attributes.
    Returns True if successful, False otherwise.
    
    Args:
        metadata: Dictionary of metadata to add
        **kwargs: Other trace attributes (name, session_id, tags, etc.)
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not LANGFUSE_CONFIGURED:
        return False
    
    try:
        client = safe_get_client()
        if not client:
            return False
        
        update_kwargs = {}
        if metadata:
            update_kwargs["metadata"] = metadata
        update_kwargs.update(kwargs)
        
        client.update_current_trace(**update_kwargs)
        return True
    except Exception:
        # Silently fail - this is expected if not in trace context
        pass
    
    return False


# ============================================================================
# Re-export from langfuse_helper for backward compatibility
# ============================================================================

if LANGFUSE_CONFIGURED:
    try:
        from src.monitoring.trace.langfuse_helper import (
            flush_langfuse,
            update_trace_with_metrics,
            update_trace_with_error,
            get_trace_url,
            observe_operation
        )
    except ImportError:
        # Fallback functions if langfuse_helper not available
        def flush_langfuse():
            pass
        
        def update_trace_with_metrics(*args, **kwargs):
            pass
        
        def update_trace_with_error(*args, **kwargs):
            pass
        
        def get_trace_url():
            return None
        
        def observe_operation(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
else:
    def flush_langfuse():
        pass
    
    def update_trace_with_metrics(*args, **kwargs):
        pass
    
    def update_trace_with_error(*args, **kwargs):
        pass
    
    def get_trace_url():
        return None
    
    def observe_operation(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

