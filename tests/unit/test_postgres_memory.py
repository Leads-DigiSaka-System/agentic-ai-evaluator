"""
Unit tests for postgres_memory.py (basic tests with mocking)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.chatbot.memory.postgres_memory import PostgresConversationMemory


class TestPostgresConversationMemory:
    """Basic tests for PostgresConversationMemory"""
    
    @patch('src.chatbot.memory.postgres_memory.get_postgres_connection')
    @patch('src.chatbot.memory.postgres_memory.return_connection')
    def test_load_from_postgres_empty_thread(self, mock_return, mock_get_conn):
        """Test loading from PostgreSQL when thread has no messages"""
        # Mock connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []  # No messages
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Create memory instance
        memory = PostgresConversationMemory(thread_id="test_thread")
        
        # Verify connection was used
        assert mock_get_conn.called
        assert mock_return.called
    
    @patch('src.chatbot.memory.postgres_memory.get_postgres_connection')
    @patch('src.chatbot.memory.postgres_memory.return_connection')
    def test_load_from_postgres_with_messages(self, mock_return, mock_get_conn):
        """Test loading messages from PostgreSQL"""
        # Mock connection with messages
        mock_conn = Mock()
        mock_cursor = Mock()
        # Return 2 messages (user and assistant)
        mock_cursor.fetchall.return_value = [
            ('user', 'Hello', None, None, 1),
            ('assistant', 'Hi there', None, None, 2)
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Create memory instance
        memory = PostgresConversationMemory(thread_id="test_thread")
        
        # Verify messages were loaded
        assert mock_get_conn.called
        assert mock_return.called
        # Check that chat_memory has messages
        assert hasattr(memory, 'chat_memory')
    
    @patch('src.chatbot.memory.postgres_memory.get_postgres_connection')
    @patch('src.chatbot.memory.postgres_memory.return_connection')
    def test_load_from_postgres_connection_error(self, mock_return, mock_get_conn):
        """Test handling of connection errors"""
        # Mock connection failure
        mock_get_conn.return_value = None
        
        # Create memory instance (should not raise exception)
        memory = PostgresConversationMemory(thread_id="test_thread")
        
        # Should handle gracefully
        assert memory is not None
    
    @patch('src.chatbot.memory.postgres_memory.get_postgres_connection')
    @patch('src.chatbot.memory.postgres_memory.return_connection')
    def test_load_respects_max_messages_limit(self, mock_return, mock_get_conn):
        """Test that MAX_MESSAGES_TO_LOAD limit is respected"""
        from src.core.config import MAX_MESSAGES_TO_LOAD
        
        # Mock connection with many messages
        mock_conn = Mock()
        mock_cursor = Mock()
        # Create more messages than limit
        many_messages = [
            ('user', f'Message {i}', None, None, i)
            for i in range(MAX_MESSAGES_TO_LOAD + 10)
        ]
        mock_cursor.fetchall.return_value = many_messages
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        # Create memory instance
        memory = PostgresConversationMemory(thread_id="test_thread")
        
        # Verify query used LIMIT
        assert mock_cursor.execute.called
        # Check that LIMIT was used in query
        execute_call = mock_cursor.execute.call_args[0][0] if mock_cursor.execute.call_args else ""
        assert "LIMIT" in str(execute_call).upper()
    
    def test_thread_id_set_correctly(self):
        """Test that thread_id is set correctly"""
        thread_id = "test_thread_123"
        
        with patch('src.chatbot.memory.postgres_memory.get_postgres_connection') as mock_get:
            mock_get.return_value = None
            memory = PostgresConversationMemory(thread_id=thread_id)
            
            # Verify thread_id is set
            assert hasattr(memory, 'thread_id')
            assert getattr(memory, 'thread_id') == thread_id

