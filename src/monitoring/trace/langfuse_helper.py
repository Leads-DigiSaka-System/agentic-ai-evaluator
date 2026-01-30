from typing import Optional, Dict, Any
from src.core.config import (
    LANGFUSE_CONFIGURED, 
    LANGFUSE_PUBLIC_KEY, 
    LANGFUSE_SECRET_KEY,
    LANGFUSE_HOST
)
from src.shared.logging.clean_logger import get_clean_logger
from functools import wraps
from typing import Callable, Any, TypeVar, ParamSpec
import inspect
logger = get_clean_logger(__name__)

# Initialize Langfuse client (v3 uses singleton pattern)
_langfuse_initialized = False

def initialize_langfuse():
    """Initialize Langfuse client once at startup (v3 pattern)"""
    global _langfuse_initialized
    
    if not LANGFUSE_CONFIGURED:
        return False
    
    if not _langfuse_initialized:
        try:
            from langfuse import Langfuse
            
            # Initialize the singleton instance
            Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST
            )
            _langfuse_initialized = True
            logger.info("✅ Langfuse v3 client initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse client: {e}")
            _langfuse_initialized = False
            return False
    
    return True


def get_langfuse_client():
    """Get the Langfuse client singleton (v3 pattern)"""
    if not LANGFUSE_CONFIGURED:
        return None
    
    try:
        from langfuse import get_client
        
        # Ensure initialized
        if not _langfuse_initialized:
            initialize_langfuse()
        
        return get_client()
    except Exception as e:
        logger.warning(f"Failed to get Langfuse client: {e}")
        return None


def flush_langfuse():
    """Flush all pending Langfuse events (v3 API)"""
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        client = get_langfuse_client()
        if client:
            client.flush()
            logger.debug("Langfuse events flushed successfully")
    except Exception as e:
        logger.warning(f"Failed to flush Langfuse: {e}")


def shutdown_langfuse():
    """Shutdown Langfuse client gracefully (v3 API)"""
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        client = get_langfuse_client()
        if client:
            client.shutdown()
            logger.debug("Langfuse client shutdown successfully")
    except Exception as e:
        logger.warning(f"Failed to shutdown Langfuse: {e}")


def update_trace_with_error(error: Exception, context: Dict[str, Any] = None):
    """Update current trace with error information (v3 API)"""
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        client = get_langfuse_client()
        if not client:
            return
        
        error_metadata = {
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        
        if context:
            error_metadata.update(context)
        
        # v3 API: Update trace via client
        client.update_current_trace(
            metadata=error_metadata
        )
        logger.debug(f"Error logged to Langfuse: {type(error).__name__}")
    except Exception as e:
        logger.warning(f"Failed to log error to Langfuse: {e}")


def update_trace_with_metrics(metrics: Dict[str, Any]):
    """Update current trace with custom metrics (v3 API)"""
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        client = get_langfuse_client()
        if not client:
            return
        
        # v3 API: Update trace via client
        client.update_current_trace(
            metadata=metrics
        )
        logger.debug(f"Metrics logged to Langfuse: {list(metrics.keys())}")
    except Exception as e:
        logger.warning(f"Failed to log metrics to Langfuse: {e}")


def create_score(
    name: str,
    value: float,
    trace_id: str = None,
    observation_id: str = None,
    data_type: str = "NUMERIC",
    comment: str = None
):
    """
    Create a score for a trace or observation (visible in dashboard)
    
    Based on Langfuse Custom Scores documentation:
    https://langfuse.com/docs/evaluation/evaluation-methods/custom-scores
    
    Args:
        name: Name of the score (e.g., "data_quality", "evaluation_confidence")
        value: Score value (float for NUMERIC, string for CATEGORICAL, 0/1 for BOOLEAN)
        trace_id: Optional trace ID (if not provided, uses current trace)
        observation_id: Optional observation ID to score a specific observation
        data_type: "NUMERIC", "CATEGORICAL", or "BOOLEAN" (defaults to NUMERIC)
        comment: Optional comment explaining the score
    """
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        client = get_langfuse_client()
        if not client:
            return
        
        # If trace_id not provided, try to get current trace ID
        # Note: Langfuse v3 doesn't have get_trace_id() method directly
        # We need to get it from the current context or observation
        if not trace_id:
            try:
                # Try to get trace ID from current observation context
                # In Langfuse v3, trace ID is typically in the context
                if hasattr(client, 'get_current_observation'):
                    obs = client.get_current_observation()
                    if obs and hasattr(obs, 'trace_id'):
                        trace_id = obs.trace_id
                # Fallback: try get_trace_id if it exists (some versions might have it)
                elif hasattr(client, 'get_trace_id'):
                    trace_id = client.get_trace_id()
            except Exception as e:
                logger.debug(f"Could not get current trace ID for scoring: {e}")
                return
        
        if not trace_id:
            logger.warning("No trace ID available for scoring")
            return
        
        # Create score using Langfuse API
        client.create_score(
            name=name,
            value=value,
            trace_id=trace_id,
            observation_id=observation_id,
            data_type=data_type,
            comment=comment
        )
        logger.debug(f"Score created: {name} = {value} (type: {data_type})")
    except Exception as e:
        logger.warning(f"Failed to create score in Langfuse: {e}")


def score_current_trace(
    name: str,
    value: float,
    data_type: str = "NUMERIC",
    comment: str = None
):
    """
    Score the current trace (convenience method)
    
    Based on Langfuse Custom Scores documentation:
    https://langfuse.com/docs/evaluation/evaluation-methods/custom-scores
    """
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        client = get_langfuse_client()
        if not client:
            return
        
        # Use score_current_trace method if available, otherwise use create_score
        try:
            client.score_current_trace(
                name=name,
                value=value,
                data_type=data_type,
                comment=comment
            )
        except AttributeError:
            # Fallback to create_score if score_current_trace not available
            trace_id = None
            try:
                # Try to get trace ID from current observation context
                if hasattr(client, 'get_current_observation'):
                    obs = client.get_current_observation()
                    if obs and hasattr(obs, 'trace_id'):
                        trace_id = obs.trace_id
                # Fallback: try get_trace_id if it exists
                elif hasattr(client, 'get_trace_id'):
                    trace_id = client.get_trace_id()
            except Exception:
                pass
            
            if trace_id:
                create_score(
                    name=name,
                    value=value,
                    trace_id=trace_id,
                    data_type=data_type,
                    comment=comment
                )
        
        logger.debug(f"Trace scored: {name} = {value}")
    except Exception as e:
        logger.warning(f"Failed to score current trace: {e}")


def get_trace_url() -> Optional[str]:
    """Get the URL of the current trace (v3 API)"""
    if not LANGFUSE_CONFIGURED:
        return None
    
    try:
        client = get_langfuse_client()
        if not client:
            return None
        
        # v3: Get trace ID from current context
        trace_id = None
        try:
            # Try to get trace ID from current observation context
            if hasattr(client, 'get_current_observation'):
                obs = client.get_current_observation()
                if obs and hasattr(obs, 'trace_id'):
                    trace_id = obs.trace_id
            # Fallback: try get_trace_id if it exists (some versions might have it)
            elif hasattr(client, 'get_trace_id'):
                trace_id = client.get_trace_id()
        except Exception:
            pass
        
        if trace_id:
            return f"{LANGFUSE_HOST}/trace/{trace_id}"
    except Exception as e:
        logger.warning(f"Failed to get trace URL: {e}")
    
    return None


def update_current_span(metadata: Dict[str, Any] = None, **kwargs):
    """
    Update the current span with metadata or other attributes (v3 helper)
    
    Args:
        metadata: Dictionary of metadata to add
        **kwargs: Other span attributes (name, output, etc.)
    """
    if not LANGFUSE_CONFIGURED:
        return
    
    try:
        # Note: In v3, spans are updated via context managers or directly on span objects
        # This is a helper for manual updates if needed
        if metadata:
            client = get_langfuse_client()
            if client:
                client.update_current_observation(metadata=metadata)
    except Exception as e:
        logger.warning(f"Failed to update current span: {e}")


# NOTE: safe_update_observation and safe_update_trace have been moved to
# src/utils/langfuse_utils.py for unified access. These functions are kept
# here for backward compatibility but will be deprecated.
# Please use: from src.shared.langfuse_utils import safe_update_observation, safe_update_trace

def safe_update_observation(metadata: Dict[str, Any] = None) -> bool:
    """
    DEPRECATED: Use src.utils.langfuse_utils.safe_update_observation instead.
    Kept for backward compatibility.
    """
    from src.shared.langfuse_utils import safe_update_observation as _safe_update
    return _safe_update(metadata)


def safe_update_trace(metadata: Dict[str, Any] = None, **kwargs) -> bool:
    """
    DEPRECATED: Use src.utils.langfuse_utils.safe_update_trace instead.
    Kept for backward compatibility.
    """
    from src.shared.langfuse_utils import safe_update_trace as _safe_update
    return _safe_update(metadata, **kwargs)

P = ParamSpec('P')
T = TypeVar('T')

def observe_operation(
    name: str = None,
    capture_input: bool = True,
    capture_output: bool = True,
    metadata: Dict[str, Any] = None
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to trace function execution with Langfuse v3.
    
    This wraps the Langfuse @observe decorator with proper error handling
    and configuration checks.
    
    Args:
        name: Custom name for the trace/span (defaults to function name)
        capture_input: Whether to capture function inputs
        capture_output: Whether to capture function outputs
        metadata: Additional metadata to attach to the trace
    
    Usage:
        @observe_operation(name="analysis_search_endpoint")
        async def analysis_search(request: AnalysisSearchRequest):
            ...
            
        @observe_operation(name="vector_search", metadata={"type": "dense"})
        def search(self, query: str, top_k: int):
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # If Langfuse not configured, return original function
        if not LANGFUSE_CONFIGURED:
            return func
        
        try:
            from langfuse import observe
            
            # Build observe kwargs
            observe_kwargs = {
                "capture_input": capture_input,
                "capture_output": capture_output
            }
            
            if name:
                observe_kwargs["name"] = name
            
            # Apply Langfuse @observe decorator
            observed_func = observe(**observe_kwargs)(func)
            
            # If metadata provided, wrap to add it
            if metadata:
                if inspect.iscoroutinefunction(func):
                    @wraps(observed_func)
                    async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                        try:
                            update_trace_with_metrics(metadata)
                        except Exception as e:
                            logger.warning(f"Failed to add metadata: {e}")
                        return await observed_func(*args, **kwargs)
                    return async_wrapper
                else:
                    @wraps(observed_func)
                    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                        try:
                            update_trace_with_metrics(metadata)
                        except Exception as e:
                            logger.warning(f"Failed to add metadata: {e}")
                        return observed_func(*args, **kwargs)
                    return sync_wrapper
            
            return observed_func
            
        except ImportError:
            logger.warning("Langfuse decorators not available, tracing disabled")
            return func
        except Exception as e:
            logger.warning(f"Failed to apply tracing decorator: {e}")
            return func
    
    return decorator