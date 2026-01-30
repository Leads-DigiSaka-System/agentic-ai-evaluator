"""
Unit tests for conversation_store.py functions
"""
import pytest
from unittest.mock import patch, Mock
from src.chatbot.memory.conversation_store import generate_thread_id


class TestGenerateThreadId:
    """Tests for generate_thread_id function"""
    
    @patch('src.monitoring.session.langfuse_session_helper.generate_session_id')
    def test_generates_thread_id_with_session(self, mock_generate_session):
        """Test that thread ID is generated correctly with session_id"""
        cooperative = "Leads"
        user_id = "user_123"
        session_id = "session_456"
        
        result = generate_thread_id(cooperative, user_id, session_id)
        
        # Should have format: chat_{cooperative}_{user_id}_{session_id}
        assert result.startswith("chat_")
        assert cooperative in result
        assert user_id in result
        assert session_id in result
        assert result == f"chat_{cooperative}_{user_id}_{session_id}"
    
    @patch('src.monitoring.session.langfuse_session_helper.generate_session_id')
    def test_prevents_duplicate_prefix(self, mock_generate_session):
        """Test that duplicate prefix is prevented"""
        cooperative = "Leads"
        user_id = "user_123"
        # Session ID already has prefix
        session_id = f"chat_{cooperative}_{user_id}_session_456"
        
        result = generate_thread_id(cooperative, user_id, session_id)
        
        # Should not add prefix again
        assert result == session_id
        assert result.count("chat_") == 1
    
    @patch('src.monitoring.session.langfuse_session_helper.generate_session_id')
    def test_generates_thread_id_without_session(self, mock_generate_session):
        """Test that thread ID is generated when session_id is None"""
        mock_generate_session.return_value = "chat_Leads_user_123_generated_session"
        cooperative = "Leads"
        user_id = "user_123"
        
        result = generate_thread_id(cooperative, user_id, None)
        
        # Should use generated session ID
        assert result.startswith("chat_")
        assert cooperative in result
        assert user_id in result
        assert mock_generate_session.called
    
    @patch('src.monitoring.session.langfuse_session_helper.generate_session_id')
    def test_thread_id_format(self, mock_generate_session):
        """Test that thread ID follows correct format"""
        cooperative = "TestCoop"
        user_id = "test_user"
        session_id = "test_session"
        
        result = generate_thread_id(cooperative, user_id, session_id)
        
        # Format: chat_{cooperative}_{user_id}_{session_id}
        expected = f"chat_{cooperative}_{user_id}_{session_id}"
        assert result == expected
    
    @patch('src.monitoring.session.langfuse_session_helper.generate_session_id')
    def test_handles_special_characters(self, mock_generate_session):
        """Test that special characters in IDs are handled correctly"""
        cooperative = "Test-Coop_123"
        user_id = "user@test.com"
        session_id = "session-123_456"
        
        result = generate_thread_id(cooperative, user_id, session_id)
        
        # Should include all parts
        assert cooperative in result
        assert user_id in result
        assert session_id in result
    
    @patch('src.monitoring.session.langfuse_session_helper.generate_session_id')
    def test_empty_strings_handled(self, mock_generate_session):
        """Test that empty strings are handled (edge case)"""
        mock_generate_session.return_value = "chat__generated"
        cooperative = ""
        user_id = ""
        
        result = generate_thread_id(cooperative, user_id, None)
        
        # Should still generate a thread ID
        assert result is not None
        assert isinstance(result, str)

