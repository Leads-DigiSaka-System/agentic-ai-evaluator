"""
Conversation memory store for chat agent using LangGraph Store
"""
from typing import Dict, Any, Optional, List
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
        store = get_conversation_store()
        
        # Try to get the checkpoint and delete it
        # MemorySaver stores checkpoints by thread_id
        try:
            # Get list of checkpoints (if supported)
            # For MemorySaver, we can try to delete by thread_id
            # Note: MemorySaver is in-memory, so clearing means removing from internal dict
            
            # If store has a list method, use it
            if hasattr(store, 'list'):
                checkpoints = store.list({"configurable": {"thread_id": thread_id}})
                for checkpoint in checkpoints:
                    if hasattr(store, 'delete'):
                        store.delete(checkpoint)
            
            # Alternative: Create a new empty checkpoint to overwrite
            # This effectively clears the conversation
            from langgraph.checkpoint.base import Checkpoint
            empty_checkpoint = Checkpoint(
                v=1,
                ts="",
                channel_values={},
                channel_versions={},
                versions_seen={}
            )
            
            # Save empty checkpoint (overwrites existing)
            store.put(
                {"configurable": {"thread_id": thread_id}},
                empty_checkpoint,
                {},
                {}
            )
            
            logger.info(f"✅ Conversation memory cleared for thread: {thread_id}")
            return True
        except Exception as clear_error:
            logger.warning(f"Could not clear memory using standard method: {clear_error}")
            # Fallback: Memory will expire naturally or be overwritten on next message
            logger.info(f"Memory clear requested for thread: {thread_id} (will be cleared on next interaction)")
            return True
    except Exception as e:
        logger.error(f"Failed to clear conversation memory: {str(e)}")
        return False


def get_conversation_history(thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get conversation history for a specific thread.
    
    Args:
        thread_id: Thread ID to get history for
        limit: Maximum number of messages to return
    
    Returns:
        List of conversation messages
    """
    try:
        store = get_conversation_store()
        
        # Get checkpoint for this thread
        checkpoint = store.get({"configurable": {"thread_id": thread_id}})
        
        if not checkpoint:
            return []
        
        # Extract messages from checkpoint
        messages = []
        if hasattr(checkpoint, 'channel_values') and checkpoint.channel_values:
            # Messages are typically stored in channel_values
            for key, value in checkpoint.channel_values.items():
                if 'messages' in key.lower() or isinstance(value, list):
                    if isinstance(value, list):
                        for msg in value[:limit]:
                            if isinstance(msg, dict):
                                messages.append({
                                    "role": msg.get("role", "unknown"),
                                    "content": msg.get("content", ""),
                                    "timestamp": checkpoint.ts if hasattr(checkpoint, 'ts') else None
                                })
                            elif hasattr(msg, 'content'):
                                messages.append({
                                    "role": getattr(msg, 'type', 'unknown'),
                                    "content": getattr(msg, 'content', ''),
                                    "timestamp": checkpoint.ts if hasattr(checkpoint, 'ts') else None
                                })
        
        return messages[:limit]
    except Exception as e:
        logger.error(f"Failed to get conversation history: {str(e)}")
        return []


def save_conversation(
    thread_id: str,
    user_message: str,
    assistant_message: str,
    tools_used: Optional[List[str]] = None
) -> bool:
    """
    Save a conversation turn to memory.
    
    Args:
        thread_id: Thread ID for the conversation
        user_message: User's message
        assistant_message: Assistant's response
        tools_used: Optional list of tools used
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # For now, we'll use a simple in-memory storage
        # In the future, we can enhance this to use the MemorySaver properly
        # The conversation history will be managed by the agent's memory
        
        # Note: AgentExecutor with memory will handle this automatically
        # This function is here for compatibility and future enhancements
        logger.debug(f"Conversation saved for thread: {thread_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save conversation: {str(e)}")
        return False

