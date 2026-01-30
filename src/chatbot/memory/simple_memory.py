"""
Conversation memory store for chat agent
Supports both in-memory (dev) and PostgreSQL (prod) storage
Compatible with LangChain 0.3.x ConversationBufferMemory and AgentExecutor
"""
from typing import Dict, Optional
from langchain.memory import ConversationBufferMemory
from src.shared.logging.clean_logger import get_clean_logger
from src.core.config import POSTGRES_URL
import os

logger = get_clean_logger(__name__)

# Global dictionary to store memories per thread_id
_thread_memories: Dict[str, ConversationBufferMemory] = {}

# Environment variable to force in-memory mode (for development)
FORCE_IN_MEMORY = os.getenv("FORCE_IN_MEMORY", "false").lower() == "true"


def get_memory_for_thread(thread_id: str) -> ConversationBufferMemory:
    """
    Get or create ConversationBufferMemory for a specific thread.
    
    Uses PostgreSQL-backed memory in production if configured, otherwise in-memory.
    
    Args:
        thread_id: Unique thread identifier (e.g., "chat_cooperative_user_session")
    
    Returns:
        ConversationBufferMemory instance for this thread (PostgresConversationMemory or ConversationBufferMemory)
    """
    global _thread_memories
    
    if thread_id not in _thread_memories:
        # Check if we should use PostgreSQL (production mode)
        use_postgres = not FORCE_IN_MEMORY and POSTGRES_URL
        
        if use_postgres:
            try:
                from src.chatbot.memory.postgres_memory import PostgresConversationMemory
                
                # Create PostgreSQL-backed memory
                memory = PostgresConversationMemory(
                    thread_id=thread_id,
                    memory_key="chat_history",
                    return_messages=True,
                    output_key="output",
                    input_key="input"
                )
                _thread_memories[thread_id] = memory
                logger.debug(f"Created PostgreSQL-backed conversation memory for thread: {thread_id}")
            except Exception as e:
                logger.warning(f"Failed to create PostgreSQL memory, falling back to in-memory: {e}")
                # Fallback to in-memory
                memory = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True,
                    output_key="output",
                    input_key="input"
                )
                _thread_memories[thread_id] = memory
                logger.debug(f"Created in-memory conversation memory for thread: {thread_id} (fallback)")
        else:
            # Use in-memory (development mode)
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="output",
                input_key="input"
            )
            _thread_memories[thread_id] = memory
            logger.debug(f"Created in-memory conversation memory for thread: {thread_id}")
    else:
        logger.debug(f"Retrieved existing conversation memory for thread: {thread_id}")
    
    return _thread_memories[thread_id]


def has_conversation_history(thread_id: str) -> bool:
    """
    Check if a thread has existing conversation history.
    
    Checks both in-memory and PostgreSQL (if using PostgresConversationMemory).
    
    Args:
        thread_id: Thread ID to check
    
    Returns:
        True if thread has conversation history, False otherwise
    """
    global _thread_memories
    
    # First check in-memory
    if thread_id in _thread_memories:
        memory = _thread_memories[thread_id]
        
        try:
            # Check if memory has any messages stored
            if hasattr(memory, 'chat_memory') and hasattr(memory.chat_memory, 'messages'):
                messages = memory.chat_memory.messages
                if len(messages) > 0:
                    return True
            elif hasattr(memory, 'buffer'):
                # Alternative check for ConversationBufferMemory
                buffer = memory.buffer
                if buffer and len(buffer) > 0:
                    return True
            else:
                # Try to load memory variables to check
                memory_vars = memory.load_memory_variables({})
                chat_history = memory_vars.get('chat_history', [])
                if len(chat_history) > 0:
                    return True
        except Exception as e:
            logger.debug(f"Could not check in-memory history for {thread_id}: {e}")
    
    # If not in-memory, check PostgreSQL (if configured)
    if not FORCE_IN_MEMORY and POSTGRES_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(POSTGRES_URL)
            cursor = conn.cursor()
            
            # Check if thread has messages in PostgreSQL
            cursor.execute("""
                SELECT COUNT(*) FROM conversation_messages WHERE thread_id = %s
            """, (thread_id,))
            
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            if count > 0:
                logger.debug(f"Found {count} messages in PostgreSQL for thread: {thread_id}")
                return True
                
        except Exception as e:
            logger.debug(f"Could not check PostgreSQL history for {thread_id}: {e}")
    
    return False


def clear_thread_memory(thread_id: str) -> bool:
    """
    Clear conversation memory for a specific thread.
    
    Clears both in-memory and PostgreSQL (if using PostgresConversationMemory).
    
    Args:
        thread_id: Thread ID to clear
    
    Returns:
        True if successful, False otherwise
    """
    global _thread_memories
    
    try:
        # Clear in-memory
        if thread_id in _thread_memories:
            # Clear the memory (this will also clear PostgreSQL if PostgresConversationMemory)
            _thread_memories[thread_id].clear()
            # Optionally remove from dict to free memory
            del _thread_memories[thread_id]
            logger.info(f"✅ Conversation memory cleared for thread: {thread_id}")
        
        # Also clear from PostgreSQL directly (in case memory wasn't loaded)
        if not FORCE_IN_MEMORY and POSTGRES_URL:
            try:
                import psycopg2
                conn = psycopg2.connect(POSTGRES_URL)
                cursor = conn.cursor()
                
                # Delete messages (CASCADE will handle thread deletion)
                cursor.execute("DELETE FROM conversation_messages WHERE thread_id = %s", (thread_id,))
                cursor.execute("DELETE FROM conversation_threads WHERE thread_id = %s", (thread_id,))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                logger.debug(f"Cleared PostgreSQL memory for thread: {thread_id}")
            except Exception as e:
                logger.debug(f"Could not clear PostgreSQL memory for {thread_id}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to clear conversation memory: {str(e)}")
        return False


def get_all_thread_ids() -> list[str]:
    """
    Get list of all active thread IDs.
    
    Returns:
        List of thread IDs with active conversations
    """
    return list(_thread_memories.keys())


def get_memory_stats() -> Dict[str, int]:
    """
    Get statistics about memory usage.
    
    Returns:
        Dictionary with memory statistics
    """
    return {
        "active_threads": len(_thread_memories),
        "total_memories": len(_thread_memories)
    }

