from typing import Optional, Dict, Any
from src.utils.config import LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_HOST
from src.utils.clean_logger import get_clean_logger
import os

logger = get_clean_logger(__name__)

# Langfuse debug mode - enable with environment variable
LANGFUSE_DEBUG = os.getenv("LANGFUSE_DEBUG", "false").lower() == "true"

def _langfuse_debug(message: str, *args, **kwargs):
    """Debug logging for Langfuse - only shows if LANGFUSE_DEBUG=true"""
    if LANGFUSE_DEBUG:
        logger.logger.debug(f"[LANGFUSE-DEBUG] {message}", *args, **kwargs)

def _langfuse_info(message: str):
    """Info logging for Langfuse - always shows"""
    logger.logger.info(f"[LANGFUSE] {message}")

# Try to import Langfuse with graceful degradation
try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    from langfuse.types import TraceContext
    # Try to import observe decorator (available in newer versions)
    try:
        from langfuse import observe as langfuse_observe
        OBSERVE_AVAILABLE = True
    except ImportError:
        langfuse_observe = None
        OBSERVE_AVAILABLE = False
    # Try to import OpenTelemetry for context management
    try:
        from opentelemetry import context, trace
        OPENTELEMETRY_AVAILABLE = True
    except ImportError:
        OPENTELEMETRY_AVAILABLE = False
        context = None
        trace = None
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None
    CallbackHandler = None
    TraceContext = None
    langfuse_observe = None
    OBSERVE_AVAILABLE = False
    OPENTELEMETRY_AVAILABLE = False
    context = None
    trace = None
    logger.warning("Langfuse not installed - pip install langfuse")

# Global Langfuse client (singleton pattern)
_langfuse_client: Optional[Any] = None


def init_langfuse() -> Optional[Any]:
    """
    Initialize Langfuse client (call once at application startup)
    
    Returns:
        Langfuse client instance or None if keys not configured or package not installed
    """
    global _langfuse_client
    
    if not LANGFUSE_AVAILABLE:
        logger.warning("Langfuse package not installed")
        return None
    
    if _langfuse_client is not None:
        logger.debug("Langfuse already initialized (reusing client)")
        return _langfuse_client
    
    if not LANGFUSE_SECRET_KEY or not LANGFUSE_PUBLIC_KEY:
        logger.warning("Langfuse keys not configured - observability disabled")
        logger.warning(f"  PUBLIC_KEY: {LANGFUSE_PUBLIC_KEY[:10] if LANGFUSE_PUBLIC_KEY else 'None'}...")
        logger.warning(f"  SECRET_KEY: {LANGFUSE_SECRET_KEY[:10] if LANGFUSE_SECRET_KEY else 'None'}...")
        logger.warning(f"  HOST: {LANGFUSE_HOST}")
        return None
    
    try:
        _langfuse_client = Langfuse(
            secret_key=LANGFUSE_SECRET_KEY,
            public_key=LANGFUSE_PUBLIC_KEY,
            host=LANGFUSE_HOST,
            debug=False  # Set to True for verbose logging
        )
        _langfuse_info("Initialized successfully")
        _langfuse_debug(f"Host: {LANGFUSE_HOST}")
        _langfuse_debug(f"Public Key: {LANGFUSE_PUBLIC_KEY[:10] if LANGFUSE_PUBLIC_KEY else 'None'}...")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_trace(
    name: str,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Optional[Any]:
    """
    Create a root trace in Langfuse with a name (shows up in dashboard)
    
    Langfuse v3.8+ uses start_span() to create traces/spans.
    A root span without a parent becomes a trace.
    
    Args:
        name: Trace name (e.g., "process_single_report", "workflow_execution")
        trace_id: Optional trace ID (auto-generated if None)
        metadata: Optional metadata dictionary
        session_id: Optional session ID for grouping
        user_id: Optional user ID for filtering
    
    Returns:
        Langfuse span object (root span = trace) or None if Langfuse not configured
    
    Usage:
        trace = create_trace(name="my_workflow", trace_id=my_id, metadata={"file": "test.pdf"})
    """
    global _langfuse_client
    
    if not LANGFUSE_AVAILABLE:
        return None
    
    if _langfuse_client is None:
        _langfuse_client = init_langfuse()
    
    if _langfuse_client is None:
        return None
    
    try:
        # Generate trace_id if not provided
        if trace_id is None:
            trace_id = create_trace_id()
        
        # Create trace context
        trace_context = TraceContext(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id
        )
        
        # Create root span which becomes a trace
        # IMPORTANT: Use start_span to create trace
        # CallbackHandler will link to this trace via trace_id in TraceContext
        span = _langfuse_client.start_span(
            name=name,
            trace_context=trace_context,
            metadata=metadata or {}
        )
        
        # End span immediately - trace_id remains valid for linking
        # CallbackHandler uses TraceContext to link generations to this trace
        span.end()
        
        # Flush immediately to ensure trace appears in dashboard
        try:
            flush_langfuse()
        except Exception as flush_err:
            logger.warning(f"Failed to flush trace on creation: {flush_err}")
        
        _langfuse_info(f"Created trace: {name}")
        _langfuse_debug(f"Trace ID: {trace_id}")
        _langfuse_debug(f"Span ID: {getattr(span, 'id', 'N/A')}")
        _langfuse_debug(f"Pass this trace_id to invoke_llm() for generations to link")
        
        # Get the actual trace URL from Langfuse client
        try:
            trace_url = _langfuse_client.get_trace_url(trace_id)
            _langfuse_debug(f"View at: {trace_url}")
        except Exception:
            # Fallback if get_trace_url doesn't work
            trace_url = f"{LANGFUSE_HOST}/trace/{trace_id}"
            _langfuse_debug(f"View at: {trace_url}")
        
        return span
    except Exception as e:
        logger.error(f"Failed to create Langfuse trace '{name}': {e}")
        import traceback
        traceback.print_exc()
        return None


def create_span(
    name: str,
    trace_id: str,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    level: str = "DEFAULT"
) -> Optional[Any]:
    """
    Create a span within a trace (for workflow nodes and operations)
    
    Args:
        name: Span name (e.g., "extraction_node", "analysis_node")
        trace_id: Parent trace ID (required)
        input_data: Input data for this span
        output_data: Output data for this span
        metadata: Additional metadata
        level: Span level (DEFAULT, DEBUG, WARNING, ERROR)
    
    Returns:
        Span object or None if Langfuse not configured
    """
    global _langfuse_client
    
    if not LANGFUSE_AVAILABLE or _langfuse_client is None:
        return None
    
    if not trace_id:
        logger.warning("Cannot create span without trace_id")
        return None
    
    try:
        # Create trace context from existing trace_id
        trace_context = TraceContext(trace_id=trace_id)
        
        # Start a span within the trace
        span = _langfuse_client.start_span(
            name=name,
            trace_context=trace_context,
            input=input_data,
            output=output_data,
            metadata=metadata or {},
            level=level
        )
        
        # End the span so it appears in dashboard
        # Note: end() doesn't take output parameter, use update first
        if output_data:
            span.update(output=output_data)
        span.end()
        
        _langfuse_debug(f"Created span: {name} in trace {trace_id}")
        return span
    except Exception as e:
        logger.error(f"Failed to create Langfuse span: {e}")
        return None


def get_langfuse_handler(
    trace_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Optional[Any]:
    """
    Create a LangChain callback handler for automatic LLM tracing
    
    This is the RECOMMENDED way to integrate Langfuse with LangChain.
    The handler automatically tracks all LLM calls, tokens, and traces.
    
    CRITICAL: Pass trace_id to link LLM generations to an existing trace.
    If trace_id is provided, the handler will link all generations to that trace.
    
    Args:
        trace_id: Optional trace ID (for linking multiple operations in same trace)
        session_id: Optional session ID (for grouping related operations)
        user_id: Optional user ID
    
    Returns:
        CallbackHandler instance or None if Langfuse not configured
    
    Usage:
        handler = get_langfuse_handler(trace_id="workflow-123")
        result = llm.invoke(prompt, config={"callbacks": [handler]})
    """
    if not LANGFUSE_AVAILABLE:
        return None
    
    if not LANGFUSE_SECRET_KEY or not LANGFUSE_PUBLIC_KEY:
        return None
    
    try:
        # Langfuse CallbackHandler configuration
        # CRITICAL FIX: Pass trace_id via TraceContext to properly link to existing trace
        handler_kwargs = {
            "public_key": LANGFUSE_PUBLIC_KEY,
            "secret_key": LANGFUSE_SECRET_KEY,
            "host": LANGFUSE_HOST,
        }
        
        # CRITICAL: Link CallbackHandler to existing trace
        # Try multiple methods to ensure trace linking works
        if trace_id:
            # Method 1: Try passing trace_id directly (most common approach)
            try:
                handler_kwargs["trace_id"] = trace_id
                _langfuse_debug(f"✅ Set trace_id directly: {trace_id}")
            except Exception as e:
                _langfuse_debug(f"Could not set trace_id directly: {e}")
            
            # Method 2: Try TraceContext (for newer versions)
            try:
                trace_context = TraceContext(
                    trace_id=trace_id,
                    session_id=session_id,
                    user_id=user_id
                )
                handler_kwargs["trace_context"] = trace_context
                _langfuse_debug(f"✅ Set trace_context: {trace_id}")
            except Exception as ctx_error:
                _langfuse_debug(f"TraceContext not supported: {ctx_error}")
            
            # Method 3: Set session_id and user_id if provided
            if session_id:
                handler_kwargs["session_id"] = session_id
            if user_id:
                handler_kwargs["user_id"] = user_id
        else:
            # No trace_id provided - handler will create new trace
            if session_id:
                handler_kwargs["session_id"] = session_id
            if user_id:
                handler_kwargs["user_id"] = user_id
        
        # Create the handler
        handler = CallbackHandler(**handler_kwargs)
        
        # Additional fallback: Try to set trace_id on handler object if supported
        if trace_id:
            try:
                if hasattr(handler, 'trace_id'):
                    handler.trace_id = trace_id
                    _langfuse_debug(f"✅ Set handler.trace_id = {trace_id}")
                elif hasattr(handler, 'set_trace_id'):
                    handler.set_trace_id(trace_id)
                    _langfuse_debug(f"✅ Called handler.set_trace_id({trace_id})")
                elif hasattr(handler, '_trace_id'):
                    handler._trace_id = trace_id
                    _langfuse_debug(f"✅ Set handler._trace_id = {trace_id}")
            except Exception as attr_error:
                _langfuse_debug(f"Could not set trace_id attribute: {attr_error}")
        
        # CRITICAL: Set OpenTelemetry context if available and trace_id provided
        # This ensures CallbackHandler can read the trace_id from context
        if trace_id and OPENTELEMETRY_AVAILABLE:
            try:
                from opentelemetry.trace import SpanContext, TraceFlags, NonRecordingSpan
                # Convert hex trace_id to integer for OpenTelemetry
                # OpenTelemetry uses 128-bit trace_id (16 bytes = 32 hex chars)
                if len(trace_id) == 32:
                    # Convert to bytes then to int
                    trace_id_bytes = bytes.fromhex(trace_id)
                    trace_id_int = int.from_bytes(trace_id_bytes[:8], byteorder='big')  # Use first 8 bytes
                    
                    span_context = SpanContext(
                        trace_id=trace_id_int,
                        span_id=0,
                        is_remote=False,
                        trace_flags=TraceFlags(TraceFlags.SAMPLED)
                    )
                    
                    # Set the context so CallbackHandler can read it
                    ctx = trace.set_span_in_context(NonRecordingSpan(span_context))
                    context.attach(ctx)
                    _langfuse_debug(f"✅ Set OpenTelemetry context for trace_id: {trace_id}")
            except Exception as otele_error:
                _langfuse_debug(f"OpenTelemetry context setup failed: {otele_error}")
        
        _langfuse_info(f"Created handler (trace_id: {trace_id if trace_id else 'auto-create'})")
        _langfuse_debug(f"Handler kwargs: {list(handler_kwargs.keys())}")
        return handler
    except Exception as e:
        logger.error(f"Failed to create Langfuse handler: {e}")
        logger.error(f"  trace_id: {trace_id}")
        logger.error(f"  Check: public_key, secret_key, and host are configured")
        import traceback
        traceback.print_exc()
        return None


def create_trace_id() -> str:
    """
    Generate a new trace ID for workflow tracking
    
    Langfuse requires trace IDs to be 32 lowercase hex characters (no dashes).
    Uses Langfuse's built-in method if available, otherwise generates hex string.
    
    Returns:
        32-character hex string trace ID
    """
    global _langfuse_client
    
    # Try to use Langfuse's built-in trace ID generator
    if _langfuse_client is None:
        _langfuse_client = init_langfuse()
    
    if _langfuse_client is not None:
        try:
            return _langfuse_client.create_trace_id()
        except Exception:
            pass
    
    # Fallback: Generate 32-char hex string (16 bytes = 32 hex chars)
    import secrets
    return secrets.token_hex(16)


def update_trace(
    trace_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    output: Optional[Any] = None
) -> None:
    """
    Update an existing trace with additional metadata or output
    
    Use this to add final metadata or output to a trace after workflow completion.
    
    Args:
        trace_id: The trace ID to update
        metadata: Optional metadata to add
        output: Optional output data
    """
    global _langfuse_client
    
    if not LANGFUSE_AVAILABLE or _langfuse_client is None:
        return
    
    if not trace_id:
        return
    
    try:
        # Create trace context
        trace_context = TraceContext(trace_id=trace_id)
        
        # Update the trace using score or update methods if available
        # Note: Langfuse v3.8+ may not have direct trace update, but spans can be updated
        logger.debug(f"Updating trace {trace_id} with metadata: {metadata}")
        
        # Flush to ensure updates are sent
        flush_langfuse()
    except Exception as e:
        logger.warning(f"Failed to update trace {trace_id}: {e}")


def flush_langfuse() -> None:
    """
    Flush all pending Langfuse events to the server
    
    CRITICAL: Call this after workflow completion to ensure traces appear in dashboard!
    Langfuse batches events for performance, so they won't appear until flushed.
    """
    global _langfuse_client
    
    if not LANGFUSE_AVAILABLE or _langfuse_client is None:
        return
    
    try:
        _langfuse_info("Flushing events...")
        _langfuse_client.flush()
        _langfuse_info("Events flushed successfully")
    except Exception as e:
        logger.error(f"Failed to flush Langfuse: {e}")
        import traceback
        traceback.print_exc()


def shutdown_langfuse() -> None:
    """
    Gracefully shutdown Langfuse (flushes and closes connection)
    Call this when your application exits
    """
    global _langfuse_client
    
    if not LANGFUSE_AVAILABLE or _langfuse_client is None:
        return
    
    try:
        _langfuse_info("Shutting down...")
        _langfuse_client.flush()
        # Note: v3.8 may not have shutdown() method
        if hasattr(_langfuse_client, 'shutdown'):
            _langfuse_client.shutdown()
        _langfuse_info("Shutdown complete")
    except Exception as e:
        logger.error(f"Failed to shutdown Langfuse: {e}")


def log_generation(
    name: str,
    trace_id: str,
    model: str,
    prompt: str,
    completion: str,
    metadata: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, int]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None
) -> Optional[Any]:
    """
    Manually log a generation to Langfuse (for direct API calls not using LangChain)
    
    Use this for direct Gemini API calls or other non-LangChain LLM invocations.
    
    Args:
        name: Generation name (e.g., "gemini_file_extraction")
        trace_id: Parent trace ID (required)
        model: Model name (e.g., "gemini-pro")
        prompt: Input prompt text (will be truncated if too long)
        completion: Output text (will be truncated if too long)
        metadata: Optional metadata dict
        usage: Optional usage dict with keys: prompt_tokens, completion_tokens, total_tokens
        start_time: Optional start timestamp (unix time)
        end_time: Optional end timestamp (unix time)
    
    Returns:
        Generation object or None if Langfuse not configured
    
    Usage:
        log_generation(
            name="gemini_file_extraction",
            trace_id=trace_id,
            model="gemini-pro",
            prompt=extraction_prompt[:2000],
            completion=extracted_text[:2000],
            metadata={"file_type": "pdf"},
            usage={"prompt_tokens": 100, "completion_tokens": 500, "total_tokens": 600}
        )
    """
    global _langfuse_client
    
    if not LANGFUSE_AVAILABLE:
        return None
    
    if _langfuse_client is None:
        _langfuse_client = init_langfuse()
    
    if _langfuse_client is None or not trace_id:
        return None
    
    try:
        # Truncate prompt/completion to avoid too large payloads
        max_text_length = 5000
        prompt_truncated = prompt[:max_text_length] if len(prompt) > max_text_length else prompt
        completion_truncated = completion[:max_text_length] if len(completion) > max_text_length else completion
        
        # Create trace context for linking
        trace_context = TraceContext(trace_id=trace_id)
        
        # Create generation
        generation = _langfuse_client.generation(
            name=name,
            trace_context=trace_context,
            model=model,
            input=prompt_truncated,
            output=completion_truncated,
            metadata=metadata or {},
            usage=usage,
            start_time=start_time,
            end_time=end_time
        )
        
        _langfuse_debug(f"Logged generation: {name} to trace {trace_id}")
        return generation
    except Exception as e:
        logger.error(f"Failed to log generation '{name}': {e}")
        return None


def observe(name: Optional[str] = None, as_root: bool = False, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs):
    """
    Wrapper for Langfuse @observe decorator
    
    This provides a clean way to use Langfuse decorators throughout your codebase.
    Based on: https://langfuse.com/docs/observability/overview
    
    Args:
        name: Name for the trace/span (defaults to function name)
        as_root: If True, creates a root trace instead of a span
        trace_id: Optional trace ID to link to existing trace
        **kwargs: Additional parameters passed to langfuse.observe()
    
    Returns:
        Decorated function with automatic tracing
        
    Usage:
        from src.utils.langfuse_helper import observe
        
        @observe(name="my_function", as_root=True)
        def my_function():
            ...
            
        @observe(trace_id="existing-trace-id")
        def workflow_node(state):
            ...
    
    Note: For LangGraph workflows, manual trace creation is still recommended
    because decorators work on function calls, not graph node execution.
    However, you can use decorators for helper functions and utilities.
    """
    if not LANGFUSE_AVAILABLE or not OBSERVE_AVAILABLE:
        # Return a no-op decorator if Langfuse or observe not available
        def no_op_decorator(func):
            return func
        return no_op_decorator
    
    if langfuse_observe is None:
        def no_op_decorator(func):
            return func
        return no_op_decorator
    
    try:
        # Handle dynamic trace_id (e.g., from lambda)
        if trace_id and callable(trace_id):
            # If trace_id is a callable, we need to handle it differently
            # For now, pass None and handle in function
            return langfuse_observe(name=name, as_root=as_root, **kwargs)
        
        return langfuse_observe(
            name=name,
            as_root=as_root,
            trace_id=trace_id,
            **kwargs
        )
    except Exception as e:
        _langfuse_debug(f"Failed to create observe decorator: {e}")
        # Return no-op decorator on error
        def no_op_decorator(func):
            return func
        return no_op_decorator


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID from Langfuse context
    
    This is used to get the trace_id created by @observe() decorator
    so it can be passed to CallbackHandler for LLM calls.
    
    Returns:
        Current trace ID or None if not available
        
    Usage:
        from src.utils.langfuse_helper import observe, get_current_trace_id
        
        @observe(as_root=True)
        def my_function():
            trace_id = get_current_trace_id()
            # Use trace_id for CallbackHandler
            ...
    """
    if not LANGFUSE_AVAILABLE or _langfuse_client is None:
        return None
    
    try:
        # Try to get current trace from Langfuse context
        # Langfuse stores trace in OpenTelemetry context
        if OPENTELEMETRY_AVAILABLE:
            try:
                from opentelemetry.trace import get_current_span
                span = get_current_span()
                if span and hasattr(span, 'context'):
                    trace_id_hex = format(span.context.trace_id, '032x')
                    return trace_id_hex
            except Exception:
                pass
        
        # Fallback: Try to get from Langfuse client if available
        # Note: This might not work in all cases, decorator context is preferred
        return None
    except Exception as e:
        _langfuse_debug(f"Failed to get current trace ID: {e}")
        return None


def estimate_tokens(text: str, method: str = "chars") -> int:
    """
    Estimate token count for text (used when actual token count unavailable)
    
    Args:
        text: Text to estimate tokens for
        method: Estimation method
            - "chars": ~4 characters per token (Gemini default)
            - "words": ~0.75 tokens per word (GPT-style)
    
    Returns:
        Estimated token count
    """
    if method == "chars":
        return len(text) // 4
    elif method == "words":
        return int(len(text.split()) * 0.75)
    else:
        return len(text) // 4
