"""
PostgreSQL-backed Conversation Memory for Chat Agent
Extends ConversationBufferMemory to persist to PostgreSQL
Compatible with LangChain 0.3.27 AgentExecutor
"""
from typing import Dict, Optional, List, Any
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from src.shared.logging.clean_logger import get_clean_logger
from src.core.config import POSTGRES_URL, MAX_MESSAGES_TO_LOAD, SESSION_TIMEOUT_MINUTES
from src.infrastructure.postgres.postgres_pool import get_postgres_connection, return_connection
import psycopg2
from psycopg2.extras import Json
import json
import re
from datetime import datetime, timedelta

logger = get_clean_logger(__name__)

# Configuration: Limit number of messages loaded from PostgreSQL
# This prevents token limit issues and keeps context relevant
# Last 10 messages = 5 conversation turns (user + assistant pairs) - Very short context
# Value is now loaded from config.py (MAX_MESSAGES_TO_LOAD env var, default: 10)


class PostgresConversationMemory(ConversationBufferMemory):
    """
    PostgreSQL-backed ConversationBufferMemory.
    Persists conversation history to PostgreSQL while maintaining ConversationBufferMemory interface.
    """
    
    def __init__(self, thread_id: str, **kwargs):
        """
        Initialize PostgreSQL-backed memory.
        
        Args:
            thread_id: Thread ID for this conversation
            **kwargs: Additional arguments for ConversationBufferMemory
        """
        super().__init__(**kwargs)
        # Use object.__setattr__ to bypass Pydantic validation for custom field
        object.__setattr__(self, 'thread_id', thread_id)
        object.__setattr__(self, '_loaded', False)
        
        # Load existing conversation from PostgreSQL
        self._load_from_postgres()
    
    def _get_connection(self):
        """
        Get PostgreSQL connection from pool.
        
        Returns:
            psycopg2 connection object or None if pool unavailable
        """
        return get_postgres_connection()
    
    def _load_from_postgres(self) -> tuple[bool, bool]:
        """
        Load conversation history from PostgreSQL.
        
        Returns:
            tuple: (loaded_successfully, session_expired)
            - loaded_successfully: True if loaded successfully, False otherwise
            - session_expired: True if session was expired and cleared, False otherwise
        """
        # Check if already loaded (using getattr to handle Pydantic model)
        if getattr(self, '_loaded', False):
            return True, False
        
        try:
            conn = self._get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            
            # Load messages from PostgreSQL
            thread_id = getattr(self, 'thread_id', None)
            if not thread_id:
                logger.error("thread_id not set in PostgresConversationMemory")
                return False
            
            # Check if session is expired (inactive for more than SESSION_TIMEOUT_MINUTES)
            cursor.execute("""
                SELECT last_message_at
                FROM conversation_threads
                WHERE thread_id = %s
            """, (thread_id,))
            
            thread_info = cursor.fetchone()
            if thread_info:
                last_message_at = thread_info[0]
                if last_message_at:
                    # Check if session expired (inactive for more than SESSION_TIMEOUT_MINUTES)
                    # Handle timezone-aware datetime from PostgreSQL
                    if isinstance(last_message_at, datetime):
                        # If timezone-aware, convert to naive for comparison
                        if last_message_at.tzinfo is not None:
                            from datetime import timezone
                            last_message_at = last_message_at.replace(tzinfo=None)
                    
                    timeout_threshold = datetime.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
                    if last_message_at < timeout_threshold:
                        logger.info(f"⏰ Session expired for thread {thread_id} (last activity: {last_message_at}, timeout: {SESSION_TIMEOUT_MINUTES} minutes)")
                        # Clear expired session
                        self.clear()
                        session_expired = True
                        return False, True  # Don't load expired session, return expired flag
                    else:
                        logger.debug(f"✅ Session active for thread {thread_id} (last activity: {last_message_at})")
            
            # Load only recent messages to prevent token limit issues
            cursor.execute("""
                SELECT message_role, message_content, tools_used, created_at, message_order
                FROM conversation_messages
                WHERE thread_id = %s
                ORDER BY message_order DESC
                LIMIT %s
            """, (thread_id, MAX_MESSAGES_TO_LOAD))
            
            rows = cursor.fetchall()
            
            # Reverse to get chronological order (oldest to newest)
            rows = list(reversed(rows))
            
            # Rebuild conversation in memory (only recent messages)
            for row in rows:
                message_role, message_content, tools_used, created_at, message_order = row
                
                if message_role == 'user':
                    self.chat_memory.add_user_message(message_content)
                elif message_role == 'assistant':
                    self.chat_memory.add_ai_message(message_content)
            
            cursor.close()
            # Return connection to pool instead of closing
            return_connection(conn)
            
            object.__setattr__(self, '_loaded', True)
            logger.debug(f"✅ Loaded {len(rows)} messages from PostgreSQL for thread: {getattr(self, 'thread_id', 'unknown')}")
            return True, False
            
        except Exception as e:
            logger.error(f"Error loading from PostgreSQL: {e}")
            # Return connection to pool even on error
            if 'conn' in locals():
                return_connection(conn)
            return False, False
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract entities (location, product, crop, applicant) from text.
        Used for context-only memory storage.
        
        Args:
            text: Text to extract entities from
        
        Returns:
            Dictionary with extracted entities
        """
        entities = {}
        text_lower = text.lower()
        
        # Common location patterns
        location_keywords = ["sa ", "location:", "lugar", "trial sa", "demo sa"]
        # Common product patterns
        product_keywords = ["product:", "produkto", "product name"]
        # Common crop patterns
        crop_keywords = ["crop:", "crop type", "palay", "corn", "rice"]
        # Common applicant patterns
        applicant_keywords = ["applicant:", "applicant name", "cooperator"]
        
        # Simple extraction - can be enhanced with NER later
        # For now, extract if keywords are present
        # Note: 're' is imported at module level to avoid scoping issues
        if any(kw in text_lower for kw in location_keywords):
            # Try to extract location after "sa " or "location:"
            location_match = re.search(r'(?:sa|location:)\s+([A-Z][a-zA-Z\s,]+)', text, re.IGNORECASE)
            if location_match:
                entities["location"] = location_match.group(1).strip()
        
        if any(kw in text_lower for kw in product_keywords):
            product_match = re.search(r'product[:\s]+([A-Z][a-zA-Z0-9\s]+)', text, re.IGNORECASE)
            if product_match:
                entities["product"] = product_match.group(1).strip()
        
        if any(kw in text_lower for kw in crop_keywords):
            crop_match = re.search(r'crop[:\s]+([A-Z][a-zA-Z\s]+)', text, re.IGNORECASE)
            if crop_match:
                entities["crop"] = crop_match.group(1).strip()
        
        return entities
    
    def _extract_query_context(self, user_input: str, tools_used: List[str] = None) -> Dict[str, Any]:
        """
        Extract query context for memory storage.
        Stores what was asked and how, not the actual data.
        
        Args:
            user_input: User's query
            tools_used: List of tools used
        
        Returns:
            Context dictionary with entities and query type
        """
        entities = self._extract_entities(user_input)
        
        # Determine query type from tools used
        query_type = "general"
        if tools_used:
            if "search_by_location_tool" in tools_used:
                query_type = "location_search"
            elif "search_by_product_tool" in tools_used:
                query_type = "product_search"
            elif "search_by_crop_tool" in tools_used:
                query_type = "crop_search"
            elif "search_by_applicant_tool" in tools_used:
                query_type = "applicant_search"
            elif "search_analysis_tool" in tools_used:
                query_type = "general_search"
        
        return {
            "query_type": query_type,
            "entities": entities,
            "tools_used": tools_used or []
        }
    
    def _save_to_postgres(self, user_input: str, ai_output: str, tools_used: List[str] = None, metadata: Dict = None) -> bool:
        """
        Save conversation turn to PostgreSQL.
        
        CONTEXT-ONLY APPROACH: Stores entities and conversation flow, NOT data values.
        This ensures memory helps construct queries but doesn't become stale.
        
        Args:
            user_input: User's message
            ai_output: Agent's response (stored for conversation flow, but entities extracted)
            tools_used: List of tools used
            metadata: Additional metadata
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            conn = self._get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            
            # Extract context (entities, query type) - NOT data values
            query_context = self._extract_query_context(user_input, tools_used)
            
            # Get thread_id safely
            thread_id = getattr(self, 'thread_id', None)
            if not thread_id:
                logger.error("thread_id not set in PostgresConversationMemory")
                return False
            
            # Get or create thread
            cursor.execute("""
                INSERT INTO conversation_threads (thread_id, cooperative, user_id, session_id, message_count, last_message_at)
                VALUES (%s, %s, %s, %s, 0, NOW())
                ON CONFLICT (thread_id) DO UPDATE
                SET message_count = conversation_threads.message_count + 2,
                    updated_at = NOW(),
                    last_message_at = NOW()
                RETURNING message_count
            """, (
                thread_id,
                self._extract_cooperative(),
                self._extract_user_id(),
                self._extract_session_id()
            ))
            
            result = cursor.fetchone()
            current_count = result[0] if result else 0
            
            # Get next message order
            cursor.execute("""
                SELECT COALESCE(MAX(message_order), 0) + 1
                FROM conversation_messages
                WHERE thread_id = %s
            """, (thread_id,))
            
            next_order = cursor.fetchone()[0]
            
            # ✅ CONTEXT-ONLY: Store user query (for conversation flow)
            # Store original query for context, but extract entities separately
            user_metadata = {
                "entities": query_context.get("entities", {}),
                "query_type": query_context.get("query_type", "general"),
                "original_query": user_input  # Keep for conversation flow
            }
            
            # Save user message with context metadata
            cursor.execute("""
                INSERT INTO conversation_messages 
                (thread_id, message_role, message_content, message_order, tools_used, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                thread_id,
                'user',
                user_input,  # Store original query for conversation flow
                next_order,
                Json(tools_used or []),
                Json(user_metadata)  # Store entities and context, NOT data
            ))
            
            # ✅ CONTEXT-ONLY: Store assistant response summary (NOT data values)
            # Extract only entities from response, don't store actual data
            response_entities = self._extract_entities(ai_output)
            
            # Create summary without data values
            # Just indicate what was found, not the actual values
            response_summary = self._create_response_summary(ai_output, tools_used)
            
            assistant_metadata = {
                "entities_found": response_entities,
                "query_type": query_context.get("query_type", "general"),
                "response_summary": response_summary,  # Summary without data values
                "tools_used": tools_used or []
            }
            
            # Save assistant message with context-only metadata
            cursor.execute("""
                INSERT INTO conversation_messages 
                (thread_id, message_role, message_content, message_order, tools_used, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                thread_id,
                'assistant',
                response_summary,  # Store summary, not full response with data
                next_order + 1,
                Json(tools_used or []),
                Json(assistant_metadata)  # Store context, NOT data values
            ))
            
            conn.commit()
            cursor.close()
            # Return connection to pool instead of closing
            return_connection(conn)
            
            logger.debug(f"💾 Saved conversation context to PostgreSQL for thread: {thread_id}")
            logger.debug(f"   Entities: {query_context.get('entities', {})}")
            logger.debug(f"   Query type: {query_context.get('query_type', 'general')}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to PostgreSQL: {e}")
            if conn:
                conn.rollback()
                # Return connection to pool even on error
                return_connection(conn)
            return False
    
    def _create_response_summary(self, ai_output: str, tools_used: List[str] = None) -> str:
        """
        Create a summary of the response without storing actual data values.
        
        Example:
            Input: "Mayroong 1 trial sa Zambales na may improvement_percent na 15%"
            Output: "Found trials in Zambales. Used search_by_location_tool."
        
        Args:
            ai_output: Full agent response
            tools_used: List of tools used
        
        Returns:
            Summary without data values
        """
        # Extract key information without data values
        summary_parts = []
        
        # Check if results were found
        if any(word in ai_output.lower() for word in ["found", "nahanap", "mayroon", "meron"]):
            summary_parts.append("Results found")
        elif any(word in ai_output.lower() for word in ["wala", "no results", "hindi nahanap"]):
            summary_parts.append("No results found")
        
        # Extract location/product/crop mentions (entities only, not values)
        entities = self._extract_entities(ai_output)
        if entities.get("location"):
            summary_parts.append(f"Location: {entities['location']}")
        if entities.get("product"):
            summary_parts.append(f"Product: {entities['product']}")
        if entities.get("crop"):
            summary_parts.append(f"Crop: {entities['crop']}")
        
        # Add tools used
        if tools_used:
            summary_parts.append(f"Tools: {', '.join(tools_used)}")
        
        return ". ".join(summary_parts) if summary_parts else "Query processed"
    
    def _extract_cooperative(self) -> str:
        """Extract cooperative from thread_id"""
        # thread_id format: chat_{cooperative}_{user_id}_{session_id}
        # Example: "chat_leads_10_test_session_001"
        thread_id = getattr(self, 'thread_id', '')
        parts = thread_id.split('_') if thread_id else []
        if len(parts) >= 2:
            return parts[1]  # cooperative
        return 'unknown'
    
    def _extract_user_id(self) -> str:
        """Extract user_id from thread_id"""
        # thread_id format: chat_{cooperative}_{user_id}_{session_id}
        # Example: "chat_leads_10_test_session_001"
        thread_id = getattr(self, 'thread_id', '')
        parts = thread_id.split('_') if thread_id else []
        if len(parts) >= 3:
            return parts[2]  # user_id
        return 'unknown'
    
    def _extract_session_id(self) -> Optional[str]:
        """Extract session_id from thread_id"""
        # thread_id format: chat_{cooperative}_{user_id}_{session_id}
        # Example: "chat_leads_10_test_session_001"
        thread_id = getattr(self, 'thread_id', '')
        parts = thread_id.split('_') if thread_id else []
        if len(parts) >= 4:
            return '_'.join(parts[3:])  # session_id (may contain underscores)
        return None
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """
        Save conversation context to both memory and PostgreSQL.
        
        Overrides ConversationBufferMemory.save_context() to add PostgreSQL persistence.
        """
        # Save to in-memory first (parent class)
        super().save_context(inputs, outputs)
        
        # Extract user input and AI output
        user_input = inputs.get(self.input_key, "")
        ai_output = outputs.get(self.output_key, "")
        
        # Extract tools_used and metadata from outputs if available
        tools_used = outputs.get("tools_used", [])
        metadata = outputs.get("metadata", {})
        
        # Save to PostgreSQL
        self._save_to_postgres(user_input, ai_output, tools_used, metadata)
    
    def clear(self) -> None:
        """
        Clear conversation from both memory and PostgreSQL.
        
        Overrides ConversationBufferMemory.clear() to also clear PostgreSQL.
        """
        # Clear in-memory
        super().clear()
        
        # Clear from PostgreSQL
        try:
            conn = self._get_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            thread_id = getattr(self, 'thread_id', None)
            if not thread_id:
                logger.warning("thread_id not set, cannot clear conversation")
                return
            
            # Delete messages (CASCADE will handle it, but explicit is better)
            cursor.execute("DELETE FROM conversation_messages WHERE thread_id = %s", (thread_id,))
            
            # Delete thread
            cursor.execute("DELETE FROM conversation_threads WHERE thread_id = %s", (thread_id,))
            
            conn.commit()
            cursor.close()
            # Return connection to pool instead of closing
            return_connection(conn)
            
            logger.info(f"🗑️ Cleared conversation from PostgreSQL for thread: {thread_id}")
            
        except Exception as e:
            logger.error(f"Error clearing from PostgreSQL: {e}")
            if conn:
                conn.rollback()
                # Return connection to pool even on error
                return_connection(conn)


def cleanup_expired_sessions(cleanup_days: int = 7) -> int:
    """
    Clean up expired sessions older than specified days.
    
    This function should be called periodically (e.g., daily cron job) to remove
    old conversation data and free up database space.
    
    Args:
        cleanup_days: Number of days old sessions to keep (default: 7)
    
    Returns:
        Number of sessions cleaned up
    """
    try:
        from src.core.config import SESSION_CLEANUP_DAYS
        cleanup_days = cleanup_days or SESSION_CLEANUP_DAYS
        
        conn = get_postgres_connection()
        if not conn:
            logger.warning("No PostgreSQL connection available for cleanup")
            return 0
        
        cursor = conn.cursor()
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=cleanup_days)
        
        # Delete old messages first (foreign key constraint)
        cursor.execute("""
            DELETE FROM conversation_messages
            WHERE thread_id IN (
                SELECT thread_id
                FROM conversation_threads
                WHERE last_message_at < %s
            )
        """, (cutoff_date,))
        messages_deleted = cursor.rowcount
        
        # Delete old threads
        cursor.execute("""
            DELETE FROM conversation_threads
            WHERE last_message_at < %s
        """, (cutoff_date,))
        threads_deleted = cursor.rowcount
        
        conn.commit()
        cursor.close()
        return_connection(conn)
        
        logger.info(f"🧹 Cleaned up {threads_deleted} expired sessions and {messages_deleted} messages (older than {cleanup_days} days)")
        return threads_deleted
        
    except Exception as e:
        logger.error(f"Error cleaning up expired sessions: {e}")
        if 'conn' in locals():
            conn.rollback()
            return_connection(conn)
        return 0

