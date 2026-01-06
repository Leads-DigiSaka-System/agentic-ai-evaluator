"""
Memory Tools - Allow agent to read and write short-term memory
Compatible with LangChain 0.3.27
"""
from langchain.tools import tool
from typing import Optional
from src.chatbot.memory.memory_manager import get_memory_manager_for_tool
from src.utils.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


@tool
def read_conversation_memory(thread_id: str) -> str:
    """
    Read short-term memory from conversation history.
    Use this tool to access previous conversation context.
    
    Args:
        thread_id: Thread ID for the conversation
    
    Returns:
        String containing conversation memory information
    """
    try:
        memory_manager = get_memory_manager_for_tool(thread_id)
        if not memory_manager:
            return f"No memory found for thread: {thread_id}"
        
        memory_data = memory_manager.read_memory()
        
        if "error" in memory_data:
            return f"Error reading memory: {memory_data['error']}"
        
        # Format memory for agent
        message_count = memory_data.get("message_count", 0)
        recent_messages = memory_data.get("recent_messages", [])
        topics = memory_data.get("topics", [])
        
        result = f"Conversation memory for thread {thread_id}:\n"
        result += f"- Total messages: {message_count}\n"
        
        if recent_messages:
            result += "\nRecent messages:\n"
            for i, msg in enumerate(recent_messages[-3:], 1):  # Last 3 messages
                msg_type = msg.get("type", "Unknown")
                content = msg.get("content", "")[:200]  # Truncate long content
                result += f"{i}. [{msg_type}]: {content}\n"
        
        if topics:
            result += f"\nRecent topics: {', '.join(topics[-3:])}\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in read_conversation_memory tool: {e}")
        return f"Error reading memory: {str(e)}"


@tool
def write_to_conversation_memory(thread_id: str, user_input: str, ai_output: str) -> str:
    """
    Write to short-term memory from tools.
    Use this tool to save important information to conversation memory.
    
    Args:
        thread_id: Thread ID for the conversation
        user_input: User input to save
        ai_output: AI output/response to save
    
    Returns:
        Confirmation message
    """
    try:
        memory_manager = get_memory_manager_for_tool(thread_id)
        if not memory_manager:
            return f"No memory found for thread: {thread_id}. Memory must be initialized first."
        
        success = memory_manager.write_to_memory(user_input, ai_output)
        
        if success:
            return f"Successfully saved to memory for thread {thread_id}"
        else:
            return f"Failed to save to memory for thread {thread_id}"
            
    except Exception as e:
        logger.error(f"Error in write_to_conversation_memory tool: {e}")
        return f"Error writing to memory: {str(e)}"


@tool
def get_conversation_summary(thread_id: str) -> str:
    """
    Get a summary of the conversation history.
    Useful for understanding what has been discussed.
    
    Args:
        thread_id: Thread ID for the conversation
    
    Returns:
        Summary of conversation
    """
    try:
        memory_manager = get_memory_manager_for_tool(thread_id)
        if not memory_manager:
            return f"No memory found for thread: {thread_id}"
        
        memory_data = memory_manager.read_memory()
        
        if "error" in memory_data:
            return f"Error reading memory: {memory_data['error']}"
        
        message_count = memory_data.get("message_count", 0)
        topics = memory_data.get("topics", [])
        recent_messages = memory_data.get("recent_messages", [])
        
        summary = f"Conversation Summary for thread {thread_id}:\n"
        summary += f"- Total messages exchanged: {message_count}\n"
        
        if topics:
            summary += f"- Topics discussed: {', '.join(set(topics))}\n"
        
        if recent_messages:
            summary += "\nRecent conversation:\n"
            for msg in recent_messages[-2:]:  # Last 2 messages
                msg_type = msg.get("type", "Unknown")
                content = msg.get("content", "")[:150]
                summary += f"  [{msg_type}]: {content}\n"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in get_conversation_summary tool: {e}")
        return f"Error getting summary: {str(e)}"

