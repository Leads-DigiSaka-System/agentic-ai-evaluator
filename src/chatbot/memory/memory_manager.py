"""
Advanced Memory Management for Chat Agent
Implements: trim, delete, summarize, topic detection, and tool access
Compatible with LangChain 0.3.27 ConversationBufferMemory
"""
from typing import Dict, Optional, List, Any, Tuple
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from src.shared.logging.clean_logger import get_clean_logger
import re

logger = get_clean_logger(__name__)

# Configuration
MAX_MESSAGES_BEFORE_TRIM = 20  # Trim when more than 20 messages
KEEP_RECENT_MESSAGES = 10  # Keep last 10 messages when trimming
MAX_MESSAGES_BEFORE_SUMMARIZE = 30  # Summarize when more than 30 messages
TOPIC_SIMILARITY_THRESHOLD = 0.3  # Topic change threshold (lower = more sensitive)


class MemoryManager:
    """
    Advanced memory manager with trim, delete, summarize, and topic detection.
    Wraps ConversationBufferMemory to add advanced features.
    """
    
    def __init__(self, memory: ConversationBufferMemory, thread_id: str):
        self.memory = memory
        self.thread_id = thread_id
        self.topic_history: List[str] = []  # Track topics for detection
        
    def get_messages(self) -> List[BaseMessage]:
        """Get all messages from memory"""
        try:
            if hasattr(self.memory, 'chat_memory') and hasattr(self.memory.chat_memory, 'messages'):
                return self.memory.chat_memory.messages
            else:
                # Load from memory variables
                memory_vars = self.memory.load_memory_variables({})
                return memory_vars.get('chat_history', [])
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []
    
    def trim_messages(self, keep_last_n: int = KEEP_RECENT_MESSAGES) -> bool:
        """
        Trim messages to keep only the last N messages.
        Keeps first message (system context) and last N messages.
        
        Args:
            keep_last_n: Number of recent messages to keep
        
        Returns:
            True if trimmed, False otherwise
        """
        try:
            messages = self.get_messages()
            if len(messages) <= keep_last_n + 1:  # +1 for first message
                return False
            
            # Keep first message (usually system/context) and last N messages
            first_msg = messages[0] if messages else None
            recent_messages = messages[-keep_last_n:] if len(messages) >= keep_last_n else messages
            
            # Clear memory and rebuild with trimmed messages
            self.memory.clear()
            
            # Re-add trimmed messages
            if first_msg:
                # Re-add first message as context
                if isinstance(first_msg, HumanMessage):
                    self.memory.chat_memory.add_user_message(first_msg.content)
                elif isinstance(first_msg, AIMessage):
                    self.memory.chat_memory.add_ai_message(first_msg.content)
            
            # Re-add recent messages
            for msg in recent_messages[1:]:  # Skip first if we already added it
                if isinstance(msg, HumanMessage):
                    self.memory.chat_memory.add_user_message(msg.content)
                elif isinstance(msg, AIMessage):
                    self.memory.chat_memory.add_ai_message(msg.content)
            
            trimmed_count = len(messages) - len(recent_messages)
            logger.info(f"✂️ Trimmed {trimmed_count} messages from thread {self.thread_id} (kept last {keep_last_n})")
            return True
            
        except Exception as e:
            logger.error(f"Error trimming messages: {e}")
            return False
    
    def delete_messages(self, message_indices: List[int] = None, delete_all: bool = False) -> bool:
        """
        Delete specific messages or all messages from memory.
        
        Args:
            message_indices: List of message indices to delete (0-based)
            delete_all: If True, delete all messages
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if delete_all:
                self.memory.clear()
                self.topic_history.clear()
                logger.info(f"🗑️ Deleted all messages from thread {self.thread_id}")
                return True
            
            if not message_indices:
                return False
            
            messages = self.get_messages()
            if not messages:
                return False
            
            # Sort indices in reverse to delete from end (preserves indices)
            sorted_indices = sorted(set(message_indices), reverse=True)
            
            # Rebuild memory without deleted messages
            new_messages = [msg for i, msg in enumerate(messages) if i not in sorted_indices]
            
            # Clear and rebuild
            self.memory.clear()
            for msg in new_messages:
                if isinstance(msg, HumanMessage):
                    self.memory.chat_memory.add_user_message(msg.content)
                elif isinstance(msg, AIMessage):
                    self.memory.chat_memory.add_ai_message(msg.content)
            
            logger.info(f"🗑️ Deleted {len(sorted_indices)} messages from thread {self.thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting messages: {e}")
            return False
    
    def summarize_old_messages(self, keep_recent: int = 5, summary_text: str = None, llm=None) -> bool:
        """
        Summarize old messages using LLM (following LangChain docs pattern).
        Keeps recent messages and replaces older ones with summary.
        
        Based on LangChain docs: https://docs.langchain.com/oss/python/langchain/short-term-memory#summarize-messages
        
        Args:
            keep_recent: Number of recent messages to keep
            summary_text: Optional summary text (if None, will be generated using LLM)
            llm: Optional LLM for summarization (if None, uses simple extraction)
        
        Returns:
            True if summarized, False otherwise
        """
        try:
            messages = self.get_messages()
            if len(messages) <= keep_recent:
                return False
            
            # Split messages: old (to summarize) and recent (to keep)
            old_messages = messages[:-keep_recent]
            recent_messages = messages[-keep_recent:]
            
            # Generate summary if not provided
            if not summary_text:
                if llm:
                    # Use LLM for summarization (LangChain docs pattern)
                    summary_text = self._generate_llm_summary(old_messages, llm)
                else:
                    # Fallback: simple keyword extraction
                    summary_text = self._generate_simple_summary(old_messages)
            
            # Rebuild memory with summary + recent messages
            # Following LangChain pattern: summary replaces old messages
            self.memory.clear()
            
            # Add summary as AI message (following LangChain pattern)
            # Format: "[Summary of previous conversation: ...]"
            self.memory.chat_memory.add_ai_message(f"[Summary of previous conversation: {summary_text}]")
            
            # Add recent messages (keep intact for context)
            for msg in recent_messages:
                if isinstance(msg, HumanMessage):
                    self.memory.chat_memory.add_user_message(msg.content)
                elif isinstance(msg, AIMessage):
                    self.memory.chat_memory.add_ai_message(msg.content)
            
            summarized_count = len(old_messages)
            logger.info(f"📝 Summarized {summarized_count} old messages in thread {self.thread_id} (kept {keep_recent} recent)")
            return True
            
        except Exception as e:
            logger.error(f"Error summarizing messages: {e}")
            return False
    
    def _generate_llm_summary(self, messages: List[BaseMessage], llm) -> str:
        """
        Generate summary using LLM (following LangChain docs pattern).
        Based on: https://docs.langchain.com/oss/python/langchain/short-term-memory#summarize-messages
        """
        try:
            from langchain_core.messages import HumanMessage
            
            # Build conversation text from messages
            conversation_text = ""
            for msg in messages:
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                content = msg.content if hasattr(msg, 'content') else str(msg)
                conversation_text += f"{role}: {content}\n\n"
            
            # Create summarization prompt (following LangChain pattern)
            summary_prompt = f"""Create a concise summary of this agricultural data query conversation.
Focus on: locations, products, crops, key findings, and important data points.

Conversation:
{conversation_text}

Summary:"""
            
            # Use LLM to generate summary
            response = llm.invoke(summary_prompt)
            summary = response.content if hasattr(response, 'content') else str(response)
            
            logger.debug(f"Generated LLM summary: {summary[:100]}...")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating LLM summary: {e}, falling back to simple summary")
            return self._generate_simple_summary(messages)
    
    def _generate_simple_summary(self, messages: List[BaseMessage]) -> str:
        """Generate a simple summary from messages (fallback when LLM not available)"""
        try:
            # Extract key information: locations, products, crops mentioned
            locations = set()
            products = set()
            crops = set()
            
            for msg in messages:
                content = msg.content if hasattr(msg, 'content') else str(msg)
                # Simple keyword extraction
                if 'zambales' in content.lower():
                    locations.add('Zambales')
                if 'laguna' in content.lower():
                    locations.add('Laguna')
                if 'product' in content.lower() or 'herbicide' in content.lower():
                    products.add('products')
                if 'crop' in content.lower() or 'rice' in content.lower() or 'palay' in content.lower():
                    crops.add('crops')
            
            summary_parts = []
            if locations:
                summary_parts.append(f"Discussed locations: {', '.join(locations)}")
            if products:
                summary_parts.append("Discussed products")
            if crops:
                summary_parts.append("Discussed crops")
            
            return "; ".join(summary_parts) if summary_parts else "Previous agricultural data queries"
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Previous conversation about agricultural data"
    
    def detect_topic_change(self, current_query: str) -> Tuple[bool, float]:
        """
        Detect if current query is a new topic compared to previous queries.
        
        Smart detection:
        - Follow-up questions (no new entities) = NOT new topic
        - Same entities = NOT new topic
        - Conflicting entities (e.g., different location) = NEW topic
        
        Args:
            current_query: Current user query
        
        Returns:
            Tuple of (is_new_topic, similarity_score)
        """
        try:
            if not self.topic_history:
                # First query, not a topic change
                self.topic_history.append(current_query.lower())
                return False, 1.0
            
            current_lower = current_query.lower()
            previous_topics = " ".join(self.topic_history[-3:])  # Compare with last 3 queries
            
            # Extract key terms (locations, products, crops, applicants)
            current_terms = self._extract_key_terms(current_lower)
            previous_terms = self._extract_key_terms(previous_topics)
            
            # Check if current query is a follow-up question (no specific entities)
            # Follow-up patterns: "ano yung", "paano", "saan", "kailan", "ilang", "magkano"
            follow_up_patterns = [
                'ano yung', 'ano ang', 'paano', 'saan', 'kailan', 'ilang', 'magkano',
                'what', 'how', 'where', 'when', 'how many', 'how much',
                'performance', 'improvement', 'result', 'summary', 'details'
            ]
            is_follow_up = any(pattern in current_lower for pattern in follow_up_patterns)
            
            # If it's a follow-up question with no new entities, it's NOT a new topic
            if is_follow_up and not current_terms:
                # Follow-up question about previous topic
                similarity = 0.8  # High similarity for follow-ups
                self.topic_history.append(current_lower)
                if len(self.topic_history) > 10:
                    self.topic_history = self.topic_history[-10:]
                logger.debug(f"Follow-up question detected (not a new topic): {current_query[:50]}...")
                return False, similarity
            
            # Check for conflicting entities (e.g., different location)
            # If current query has a location/product/crop that conflicts with previous
            current_locations = [t for t in current_terms if t in ['zambales', 'laguna', 'bulacan', 'nueva ecija', 'pampanga', 'tarlac']]
            previous_locations = [t for t in previous_terms if t in ['zambales', 'laguna', 'bulacan', 'nueva ecija', 'pampanga', 'tarlac']]
            
            # If current has a different location than previous, it's a new topic
            if current_locations and previous_locations:
                if not any(loc in previous_locations for loc in current_locations):
                    # Different location = new topic
                    logger.info(f"🆕 New topic detected: different location ({current_locations} vs {previous_locations})")
                    self.topic_history.append(current_lower)
                    if len(self.topic_history) > 10:
                        self.topic_history = self.topic_history[-10:]
                    return True, 0.0
            
            # Calculate similarity based on common terms
            if not previous_terms:
                similarity = 0.0
            else:
                common_terms = len(set(current_terms) & set(previous_terms))
                total_terms = len(set(current_terms) | set(previous_terms))
                similarity = common_terms / total_terms if total_terms > 0 else 0.0
                
                # If current has terms but no overlap with previous, might be new topic
                if current_terms and common_terms == 0:
                    similarity = 0.0
            
            # Only detect as new topic if similarity is very low AND has conflicting entities
            is_new_topic = similarity < TOPIC_SIMILARITY_THRESHOLD and (current_terms or not is_follow_up)
            
            if is_new_topic:
                logger.info(f"🆕 New topic detected in thread {self.thread_id} (similarity: {similarity:.2f})")
            
            # Update topic history
            self.topic_history.append(current_lower)
            if len(self.topic_history) > 10:  # Keep last 10 topics
                self.topic_history = self.topic_history[-10:]
            
            return is_new_topic, similarity
            
        except Exception as e:
            logger.error(f"Error detecting topic change: {e}")
            return False, 0.0
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms (locations, products, crops) from text"""
        terms = []
        
        # Common locations
        locations = ['zambales', 'laguna', 'bulacan', 'nueva ecija', 'pampanga', 'tarlac']
        for loc in locations:
            if loc in text:
                terms.append(loc)
        
        # Products
        if any(word in text for word in ['herbicide', 'fungicide', 'insecticide', 'fertilizer', 'product']):
            terms.append('product')
        
        # Crops
        if any(word in text for word in ['rice', 'palay', 'corn', 'crop']):
            terms.append('crop')
        
        # Trials/demos
        if any(word in text for word in ['trial', 'demo', 'test']):
            terms.append('trial')
        
        return terms
    
    def auto_manage_memory(self, current_query: str, llm=None) -> Dict[str, Any]:
        """
        Automatically manage memory: trim, summarize, detect topic changes.
        Called before each invoke.
        
        Following LangChain docs pattern:
        - Summarize when message count exceeds threshold (using LLM)
        - Trim when still too many messages
        - Detect topic changes and delete irrelevant history
        
        Args:
            current_query: Current user query
            llm: Optional LLM for summarization (following LangChain SummarizationMiddleware pattern)
        
        Returns:
            Dict with management actions taken
        """
        actions = {
            "trimmed": False,
            "summarized": False,
            "topic_changed": False,
            "deleted_old": False
        }
        
        try:
            messages = self.get_messages()
            message_count = len(messages)
            
            # 1. Detect topic change (delete irrelevant past conversations)
            is_new_topic, similarity = self.detect_topic_change(current_query)
            if is_new_topic:
                actions["topic_changed"] = True
                # Delete old messages if topic changed significantly
                # When topic changes, we want to clear old context to avoid confusion
                # Keep only the most recent message (last agent response) for minimal context
                if message_count >= 2:
                    # Delete all except last 1 message (keep last agent response only)
                    # This ensures new topic starts fresh but keeps minimal context
                    indices_to_delete = list(range(message_count - 1))
                    if indices_to_delete:
                        success = self.delete_messages(message_indices=indices_to_delete)
                        if success:
                            actions["deleted_old"] = True
                            logger.info(f"🗑️ Deleted {len(indices_to_delete)} old messages due to topic change in thread {self.thread_id} (kept last 1 message)")
                        else:
                            logger.warning(f"⚠️ Failed to delete old messages on topic change")
                elif message_count == 1:
                    # Only 1 message, clear it completely for new topic
                    self.memory.clear()
                    actions["deleted_old"] = True
                    logger.info(f"🗑️ Cleared memory due to topic change in thread {self.thread_id}")
                else:
                    logger.debug(f"No messages to delete on topic change (only {message_count} messages)")
            
            # 2. Summarize if too many messages (following LangChain SummarizationMiddleware pattern)
            # LangChain docs: trigger=("messages", 30) or trigger=("tokens", 4000)
            if message_count > MAX_MESSAGES_BEFORE_SUMMARIZE:
                # Use LLM for summarization if available (following LangChain pattern)
                self.summarize_old_messages(keep_recent=5, llm=llm)
                actions["summarized"] = True
            
            # 3. Trim if still too many (fallback if summarization didn't help enough)
            messages_after = self.get_messages()
            if len(messages_after) > MAX_MESSAGES_BEFORE_TRIM:
                self.trim_messages(keep_last_n=KEEP_RECENT_MESSAGES)
                actions["trimmed"] = True
            
            return actions
            
        except Exception as e:
            logger.error(f"Error in auto_manage_memory: {e}")
            return actions
    
    def read_memory(self) -> Dict[str, Any]:
        """
        Read memory for tools (read short-term memory in a tool).
        Returns memory state that tools can access.
        
        Returns:
            Dict with memory information
        """
        try:
            messages = self.get_messages()
            memory_vars = self.memory.load_memory_variables({})
            
            return {
                "thread_id": self.thread_id,
                "message_count": len(messages),
                "chat_history": memory_vars.get('chat_history', []),
                "recent_messages": [
                    {
                        "type": type(msg).__name__,
                        "content": msg.content if hasattr(msg, 'content') else str(msg)
                    }
                    for msg in messages[-5:]  # Last 5 messages
                ],
                "topics": self.topic_history[-5:] if self.topic_history else []
            }
            
        except Exception as e:
            logger.error(f"Error reading memory: {e}")
            return {"error": str(e)}
    
    def write_to_memory(self, user_input: str, ai_output: str) -> bool:
        """
        Write to memory from tools (write short-term memory from tools).
        Allows tools to save information to memory.
        
        Args:
            user_input: User input to save
            ai_output: AI output to save
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.memory.save_context(
                {"input": user_input},
                {"output": ai_output}
            )
            logger.debug(f"💾 Tool wrote to memory for thread {self.thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing to memory: {e}")
            return False


# Global registry of memory managers
_memory_managers: Dict[str, MemoryManager] = {}


def get_memory_manager(thread_id: str, memory: ConversationBufferMemory) -> MemoryManager:
    """
    Get or create MemoryManager for a thread.
    
    Args:
        thread_id: Thread ID
        memory: ConversationBufferMemory instance
    
    Returns:
        MemoryManager instance
    """
    global _memory_managers
    
    if thread_id not in _memory_managers:
        _memory_managers[thread_id] = MemoryManager(memory, thread_id)
        logger.debug(f"Created MemoryManager for thread: {thread_id}")
    
    return _memory_managers[thread_id]


def get_memory_manager_for_tool(thread_id: str) -> Optional[MemoryManager]:
    """
    Get MemoryManager for tools to access memory.
    Used by tools that need to read/write memory.
    
    Args:
        thread_id: Thread ID
    
    Returns:
        MemoryManager if exists, None otherwise
    """
    global _memory_managers
    return _memory_managers.get(thread_id)

