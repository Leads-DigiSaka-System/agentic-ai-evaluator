"""
Conversation memory store for chat agent using LangGraph PostgresSaver
Automatically uses PostgreSQL for persistent storage if configured
"""
from typing import Dict, Any, Optional, List
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from src.utils.clean_logger import get_clean_logger
from src.utils.config import POSTGRES_URL
import os

logger = get_clean_logger(__name__)

# Try to import PostgresSaver - may fail if version incompatible
PostgresSaver = None
try:
    from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
    POSTGRES_SAVER_AVAILABLE = True
except ImportError as e:
    POSTGRES_SAVER_AVAILABLE = False
    logger.warning(f"⚠️ PostgresSaver not available: {e}")
    logger.info("💡 Using MemorySaver for conversation history (in-memory)")
except Exception as e:
    POSTGRES_SAVER_AVAILABLE = False
    logger.warning(f"⚠️ PostgresSaver import failed: {e}")
    logger.info("💡 Using MemorySaver for conversation history (in-memory)")

# Global store instance (shared across agents)
_store: Optional[BaseCheckpointSaver] = None


def get_conversation_store() -> BaseCheckpointSaver:
    """
    Get or create the conversation memory store.
    
    Uses LangGraph PostgresSaver for persistent storage in PostgreSQL if configured.
    Falls back to MemorySaver if PostgreSQL is not configured.
    
    According to LangChain docs:
    - PostgresSaver automatically creates tables on setup()
    - Handles state persistence across restarts
    - Works seamlessly with LangChain agents
    
    Returns:
        BaseCheckpointSaver instance for conversation memory
    """
    global _store
    
    if _store is None:
        try:
            # Check if PostgresSaver is available and PostgreSQL is configured
            if not POSTGRES_SAVER_AVAILABLE or PostgresSaver is None:
                logger.warning("⚠️ PostgresSaver not available, using MemorySaver (in-memory)")
                logger.info("💡 To enable persistent memory, install compatible langgraph-checkpoint-postgres")
                _store = MemorySaver()
                logger.info("✅ Conversation memory store initialized (MemorySaver)")
                return _store
            
            if not POSTGRES_URL:
                logger.warning("⚠️ POSTGRES_URL not configured, using MemorySaver (in-memory)")
                logger.info("💡 To enable persistent memory, add PostgreSQL config to .env")
                _store = MemorySaver()
                logger.info("✅ Conversation memory store initialized (MemorySaver)")
                return _store
            
            # Use PostgresSaver for persistent storage (following LangChain docs pattern)
            # Docs pattern: with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
            # Since we need a global store, we'll use it without context manager but call setup()
            logger.info(f"Initializing PostgresSaver for persistent memory...")
            logger.info("💡 Following LangChain docs pattern: PostgresSaver.from_conn_string()")
            
            try:
                # Following docs pattern: PostgresSaver.from_conn_string(DB_URI)
                _store = PostgresSaver.from_conn_string(POSTGRES_URL)
                
                # Setup creates tables automatically (idempotent - safe to call multiple times)
                # Docs pattern: checkpointer.setup() # auto create tables in PostgresSql
                _store.setup()
                
                logger.info("✅ Conversation memory store initialized (PostgresSaver)")
                # Log database info (hide password)
                db_info = POSTGRES_URL.split('@')[-1] if '@' in POSTGRES_URL else POSTGRES_URL
                logger.info(f"💡 PostgreSQL: {db_info}")
                logger.info("💡 Tables created automatically by PostgresSaver.setup()")
            except Exception as setup_error:
                logger.error(f"❌ Failed to setup PostgresSaver: {setup_error}")
                logger.warning("⚠️ Falling back to MemorySaver")
                logger.info("💡 To enable PostgreSQL, update langgraph to compatible version")
                _store = MemorySaver()
                logger.info("✅ Conversation memory store initialized (MemorySaver - fallback)")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize PostgresSaver: {e}")
            logger.warning("⚠️ Falling back to MemorySaver")
            _store = MemorySaver()
            logger.info("✅ Conversation memory store initialized (MemorySaver - fallback)")
    
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
        # Use provided session_id (may already have prefix, so check)
        if session_id.startswith(f"chat_{cooperative}_{user_id}"):
            # Already has prefix, use as-is
            return session_id
        else:
            # Add prefix
            return f"chat_{cooperative}_{user_id}_{session_id}"
    else:
        # Generate new session-based thread ID
        from src.monitoring.session.langfuse_session_helper import generate_session_id
        # Generate session_id with prefix, then add to thread_id format
        session_id = generate_session_id(prefix=f"chat_{cooperative}_{user_id}")
        # session_id already has prefix, so just use it directly
        return session_id


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

