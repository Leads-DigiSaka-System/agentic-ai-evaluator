import uuid
from typing import Optional, Dict, Any, ContextManager
from contextlib import contextmanager
from src.core.config import LANGFUSE_CONFIGURED
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)

# Import Langfuse propagate_attributes if available (v3 API)
if LANGFUSE_CONFIGURED:
    try:
        from langfuse import propagate_attributes
        LANGFUSE_SESSION_AVAILABLE = True
    except ImportError:
        LANGFUSE_SESSION_AVAILABLE = False
else:
    LANGFUSE_SESSION_AVAILABLE = False

# Fallback stub if propagate_attributes is not available
if not LANGFUSE_SESSION_AVAILABLE:
    @contextmanager
    def propagate_attributes(*args, **kwargs):
        yield

# Store current session ID in context (thread-local or similar)
_current_session_id: Optional[str] = None


def generate_session_id(prefix: str = "session") -> str:
    """
    Generate a unique session ID for Langfuse.
    
    Session IDs must be:
    - US-ASCII character strings
    - Less than 200 characters
    - Unique identifiers for the session
    
    Args:
        prefix: Optional prefix for the session ID (default: "session")
        
    Returns:
        A unique session ID string (format: {prefix}-{uuid4})
        
    Example:
        >>> session_id = generate_session_id("chat")
        >>> # Returns: "chat-550e8400-e29b-41d4-a716-446655440000"
    """
    session_uuid = str(uuid.uuid4())
    session_id = f"{prefix}-{session_uuid}"
    
    # Ensure it's under 200 characters (Langfuse requirement)
    if len(session_id) > 200:
        # If prefix is too long, just use UUID
        session_id = session_uuid
        logger.warning(f"Session prefix '{prefix}' too long, using UUID only")
    
    return session_id


def get_current_session_id() -> Optional[str]:
    """
    Get the current session ID if one is set.
    
    Returns:
        Current session ID string or None if not set
    """
    return _current_session_id


def set_current_session_id(session_id: Optional[str]) -> None:
    """
    Set the current session ID (internal use).
    
    Args:
        session_id: Session ID to set, or None to clear
    """
    global _current_session_id
    _current_session_id = session_id


@contextmanager
def propagate_session_id(session_id: str, **additional_attributes) -> ContextManager[None]:
    """
    Context manager to propagate session_id to all child observations.
    
    This uses Langfuse's propagate_attributes to ensure all observations
    created within this context inherit the session_id. This is the
    recommended way to set session IDs according to Langfuse documentation.
    
    Args:
        session_id: Session ID to propagate (must be ≤200 chars, US-ASCII)
        **additional_attributes: Additional attributes to propagate (user_id, etc.)
                                Note: Only string values are supported by Langfuse
        
    Yields:
        None (context manager)
        
    Example:
        >>> with propagate_session_id("chat-session-123"):
        ...     # All observations created here will have session_id
        ...     result = process_chat_message()
        ...     # OpenAI calls, LangChain chains, etc. will all inherit session_id
    """
    if not LANGFUSE_CONFIGURED or not LANGFUSE_SESSION_AVAILABLE:
        logger.debug("Langfuse not configured, skipping session propagation")
        yield
        return
    
    # Validate session_id length (Langfuse requirement)
    if len(session_id) > 200:
        logger.warning(
            f"Session ID '{session_id[:50]}...' exceeds 200 characters, "
            "it will be dropped by Langfuse"
        )
    
    try:
        # Prepare attributes dict - only include session_id and valid string attributes
        # Langfuse requires all attribute values to be strings ≤200 chars
        attributes = {"session_id": session_id}
        
        # Filter and convert additional attributes to strings (Langfuse requirement)
        for key, value in additional_attributes.items():
            if value is not None:
                # Convert to string and truncate if too long
                str_value = str(value)
                if len(str_value) > 200:
                    str_value = str_value[:200]
                    logger.debug(f"Attribute '{key}' truncated to 200 characters")
                attributes[key] = str_value
        
        # Set current session ID for reference
        old_session_id = _current_session_id
        set_current_session_id(session_id)
        
        try:
            # Use Langfuse's propagate_attributes context manager
            # This works in both sync and async contexts
            with propagate_attributes(**attributes):
                yield
        finally:
            # Restore previous session ID
            set_current_session_id(old_session_id)
            
    except Exception as e:
        logger.warning(f"Failed to propagate session ID: {e}")
        # Still yield even if propagation fails to avoid breaking the code flow
        yield


class SessionContextManager:
    """
    Alternative class-based approach for session management.
    
    This provides a more explicit API for managing sessions with
    automatic cleanup and error handling.
    
    Example:
        >>> session = SessionContextManager("chat-session-123")
        >>> with session:
        ...     # All observations inherit session_id
        ...     process_request()
    """
    
    def __init__(self, session_id: str, **additional_attributes):
        """
        Initialize session context manager.
        
        Args:
            session_id: Session ID to propagate
            **additional_attributes: Additional attributes to propagate
        """
        self.session_id = session_id
        self.additional_attributes = additional_attributes
        self._context_manager = None
        
    def __enter__(self):
        """Enter session context."""
        self._context_manager = propagate_session_id(
            self.session_id,
            **self.additional_attributes
        )
        return self._context_manager.__enter__()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit session context."""
        if self._context_manager:
            return self._context_manager.__exit__(exc_type, exc_val, exc_tb)
        return False


def create_session_for_request(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    prefix: str = "request"
) -> str:
    """
    Create a session ID for a request/API call.
    
    This is a convenience function that generates a session ID and optionally
    includes request/user context.
    
    Args:
        request_id: Optional request ID to include in session
        user_id: Optional user ID to include in session
        prefix: Prefix for session ID (default: "request")
        
    Returns:
        Generated session ID string
        
    Example:
        >>> session_id = create_session_for_request(
        ...     request_id="req-123",
        ...     user_id="user-456"
        ... )
        >>> with propagate_session_id(session_id, user_id="user-456"):
        ...     process_request()
    """
    if request_id:
        # Use request_id as part of session ID if provided
        session_id = f"{prefix}-{request_id}"
        if len(session_id) > 200:
            # Fallback to generated ID if too long
            session_id = generate_session_id(prefix)
    else:
        session_id = generate_session_id(prefix)
    
    return session_id


def get_session_url(session_id: str) -> Optional[str]:
    """
    Get the Langfuse dashboard URL for a session.
    
    Args:
        session_id: The session ID to get URL for
        
    Returns:
        URL string or None if Langfuse not configured
    """
    if not LANGFUSE_CONFIGURED:
        return None
    
    try:
        from src.core.config import LANGFUSE_HOST
        # Langfuse session URLs follow this pattern
        return f"{LANGFUSE_HOST}/sessions/{session_id}"
    except Exception as e:
        logger.warning(f"Failed to generate session URL: {e}")
        return None


# Convenience function for use with @observe decorator
def with_session(session_id: str, **additional_attributes):
    """
    Decorator helper to wrap a function with session propagation.
    
    This is useful when you want to add session support to an existing
    @observe decorated function.
    
    Args:
        session_id: Session ID to propagate
        **additional_attributes: Additional attributes to propagate
        
    Example:
        >>> @observe(name="my_function")
        ... def my_function():
        ...     with propagate_session_id("session-123"):
        ...         # your code here
        ...         pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with propagate_session_id(session_id, **additional_attributes):
                return func(*args, **kwargs)
        return wrapper
    return decorator

