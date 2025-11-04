from typing import Optional, Dict, Any
from src.utils.config import (
    LANGFUSE_CONFIGURED, 
    LANGFUSE_PUBLIC_KEY, 
    LANGFUSE_SECRET_KEY,
    LANGFUSE_HOST
)
from src.utils.clean_logger import get_clean_logger

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


def get_trace_url() -> Optional[str]:
    """Get the URL of the current trace (v3 API)"""
    if not LANGFUSE_CONFIGURED:
        return None
    
    try:
        client = get_langfuse_client()
        if not client:
            return None
        
        # v3: Get trace ID from current context
        trace_id = client.get_trace_id()
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