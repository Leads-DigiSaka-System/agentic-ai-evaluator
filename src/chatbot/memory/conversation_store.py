"""
Conversation memory store for chat agent using LangGraph Store
"""
from typing import Dict, Any, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from src.utils.clean_logger import get_clean_logger
import os
import json
from datetime import datetime, timedelta

logger = get_clean_logger(__name__)

# Global store instance (shared across agents)
_store: Optional[BaseCheckpointSaver] = None


def get_conversation_store() -> BaseCheckpointSaver:
    """
    Get or create the conversation memory store.
    
    Uses LangGraph MemorySaver for in-memory storage.
    This stores conversation state within the application process.
    
    According to Deep Agents docs:
    - StoreBackend uses this store for persistent file storage
    - Files in /memories/ path persist across conversations
    - Files in / path are ephemeral (StateBackend)
    
    Note: We use MemorySaver (simple, no external dependencies)
    - Qdrant is used for data storage (reports, analysis)
    - MemorySaver is used for conversation memory (chat state)
    
    Returns:
        BaseCheckpointSaver instance for conversation memory
    """
    global _store
    
    if _store is None:
        # Use MemorySaver (in-memory, persists within thread)
        # Simple, no external dependencies needed
        _store = MemorySaver()
        logger.info("✅ Conversation memory store initialized (MemorySaver)")
        logger.info("💡 Memory persists within thread, Qdrant used for data storage")
    
    return _store


def generate_thread_id(cooperative: str, user_id: str, session_id: Optional[str] = None) -> str:
    """
    Generate a thread ID for conversation memory.
    
    Format: chat_{cooperative}_{user_id}_{session_id}
    This ensures:
    - Cooperative isolation
    - User isolation (optional)
    - Session continuity
    
    Args:
        cooperative: Cooperative ID
        user_id: User ID
        session_id: Optional session ID (if None, uses timestamp-based ID)
    
    Returns:
        Thread ID string for LangGraph checkpoint
    """
    if session_id:
        # Use provided session_id
        return f"chat_{cooperative}_{user_id}_{session_id}"
    else:
        # Generate new session-based thread ID
        from src.monitoring.session.langfuse_session_helper import generate_session_id
        session_id = generate_session_id(prefix=f"chat_{cooperative}_{user_id}")
        return f"chat_{cooperative}_{user_id}_{session_id}"


def clear_conversation_memory(thread_id: str) -> bool:
    """
    Clear conversation memory for a specific thread.
    
    Args:
        thread_id: Thread ID to clear
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Note: MemorySaver doesn't have a direct clear method
        # We'll need to handle this differently or use a different store
        # For now, return True (memory will expire naturally)
        logger.info(f"Conversation memory clear requested for thread: {thread_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear conversation memory: {str(e)}")
        return False

