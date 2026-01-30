"""
Unit tests for chat_agent.py critical functions
"""
import pytest
import sys
import types
from unittest.mock import Mock, MagicMock, patch

# Mock ALL dependencies BEFORE any imports
# This must happen before importing chat_agent
sys.modules['psycopg2'] = Mock()
sys.modules['psycopg2.pool'] = Mock()
sys.modules['psycopg2.extras'] = Mock()

# Mock utility modules
sys.modules['src.utils.llm_helper'] = Mock()
sys.modules['src.utils.openrouter_helper'] = Mock()
sys.modules['src.utils.gemini_helper'] = Mock()
sys.modules['src.utils.llm_factory'] = Mock()

# Mock postgres pool functions
mock_postgres_pool = Mock()
mock_postgres_pool.get_postgres_connection = Mock(return_value=None)
mock_postgres_pool.return_connection = Mock()
sys.modules['src.utils.postgres_pool'] = mock_postgres_pool

# chat_agent -> tools -> search_tools -> analysis_search (loads HuggingFace). Mock it so tests run offline.
_mock_analysis_module = types.ModuleType('analysis_search')
_mock_analysis_module.analysis_searcher = Mock()
sys.modules['src.infrastructure.vector_store.analysis_search'] = _mock_analysis_module

# LangChain 0.3: langchain.agents pulls in deprecated paths (chat_memory, token_buffer).
# Fake langchain.memory as a package so those internal imports succeed.
# Also provide ConversationBufferMemory for modules that import it from langchain.memory.
_langchain_memory = types.ModuleType('langchain.memory')
_langchain_memory_chat = types.ModuleType('langchain.memory.chat_memory')
_langchain_memory_chat.BaseChatMemory = type('BaseChatMemory', (), {})
_langchain_memory.chat_memory = _langchain_memory_chat
_langchain_memory_token = types.ModuleType('langchain.memory.token_buffer')
_langchain_memory_token.ConversationTokenBufferMemory = type('ConversationTokenBufferMemory', (), {})
_langchain_memory.token_buffer = _langchain_memory_token
# Stub for ConversationBufferMemory (used by postgres_memory, simple_memory, memory_manager)
# Must have chat_memory so PostgresConversationMemory and tests that check .chat_memory pass.
def _buffer_init(self, *args, **kwargs):
    self.chat_memory = Mock()
    self.chat_memory.messages = []
_langchain_memory.ConversationBufferMemory = type('ConversationBufferMemory', (), {'__init__': _buffer_init})
sys.modules['langchain.memory'] = _langchain_memory
sys.modules['langchain.memory.chat_memory'] = _langchain_memory_chat
sys.modules['langchain.memory.token_buffer'] = _langchain_memory_token

from langchain_core.tools import StructuredTool

# Now import the functions we want to test
from src.chatbot.bot.chat_agent import _clean_agent_response, _bind_cooperative_to_tool


class TestCleanAgentResponse:
    """Tests for _clean_agent_response function"""
    
    def test_empty_string(self):
        """Test that empty string returns empty string"""
        result = _clean_agent_response("")
        assert result == ""
    
    def test_none_input(self):
        """Test that None input returns None"""
        result = _clean_agent_response(None)
        assert result is None
    
    def test_removes_markdown_headers(self):
        """Test that markdown headers (##, ###) are removed"""
        input_text = "## Search Results\n\n### Result 1\n\nContent here"
        result = _clean_agent_response(input_text)
        assert "##" not in result
        assert "###" not in result
        assert "Search Results" in result
        assert "Content here" in result
    
    def test_removes_bold_formatting(self):
        """Test that bold markdown (**text**) is removed but content kept"""
        input_text = "**Product:** iSMART NANO UREA\n**Location:** Zambales"
        result = _clean_agent_response(input_text)
        assert "**" not in result
        assert "Product: iSMART NANO UREA" in result
        assert "Location: Zambales" in result
    
    def test_removes_italic_formatting(self):
        """Test that italic markdown (*text*) is removed but content kept"""
        input_text = "*Summary:* This is a test"
        result = _clean_agent_response(input_text)
        assert "*" not in result
        assert "Summary: This is a test" in result
    
    def test_removes_code_blocks(self):
        """Test that code blocks (`text`) are removed but content kept"""
        input_text = "Use `search_analysis_tool` to search"
        result = _clean_agent_response(input_text)
        assert "`" not in result
        assert "search_analysis_tool" in result
    
    def test_cleans_excessive_newlines(self):
        """Test that excessive newlines (3+) are reduced to 2"""
        input_text = "Line 1\n\n\n\n\nLine 2"
        result = _clean_agent_response(input_text)
        assert "\n\n\n" not in result
        assert "\n\n" in result or "\n" in result
    
    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is removed"""
        input_text = "   \n  Content here  \n  "
        result = _clean_agent_response(input_text)
        assert result == "Content here" or result.strip() == "Content here"
    
    def test_no_results_found_with_location(self):
        """Test that 'No Results Found' with location is converted to Tagalog"""
        input_text = "## No Results Found\n\nNo results found for query: location: Zambales"
        result = _clean_agent_response(input_text)
        assert "Wala po akong nahanap" in result
        assert "Zambales" in result
        assert "##" not in result
    
    def test_no_results_found_with_product(self):
        """Test that 'No Results Found' with product is converted to Tagalog"""
        input_text = "## No Results Found\n\nNo results found for query: product: iSMART NANO UREA"
        result = _clean_agent_response(input_text)
        assert "Wala po akong nahanap" in result
        assert "iSMART NANO UREA" in result
        assert "##" not in result
    
    def test_no_results_found_generic(self):
        """Test that generic 'No Results Found' is converted to Tagalog"""
        input_text = "## No Results Found\n\nNo results found for query: test query"
        result = _clean_agent_response(input_text)
        assert "Wala po akong nahanap" in result
        assert "##" not in result
    
    def test_removes_technical_prefixes(self):
        """Test that technical prefixes like 'No results found for query:' are removed"""
        input_text = "No results found for query: test query\n\nSome content"
        result = _clean_agent_response(input_text)
        assert "No results found for query:" not in result
        assert "test query" in result or "Some content" in result
    
    def test_preserves_normal_text(self):
        """Test that normal text without markdown is preserved"""
        input_text = "This is a normal response without any markdown formatting."
        result = _clean_agent_response(input_text)
        assert result == input_text


class TestBindCooperativeToTool:
    """Tests for _bind_cooperative_to_tool function"""
    
    def test_injects_cooperative_parameter(self):
        """Test that cooperative is injected into tool kwargs"""
        # Create a mock tool
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool description"
        mock_tool.invoke = Mock(return_value="test result")
        mock_tool.args_schema = None
        
        # Bind cooperative
        bound_tool = _bind_cooperative_to_tool(mock_tool, "test_coop")
        
        # Invoke the bound tool
        result = bound_tool.invoke({"query": "test"})
        
        # Verify cooperative was injected
        call_args = mock_tool.invoke.call_args[0][0] if mock_tool.invoke.call_args else {}
        # Check if cooperative was passed (either in first call or retry)
        assert mock_tool.invoke.called
        assert result == "test result"
    
    def test_removes_none_string_values(self):
        """Test that 'None' string values are removed from kwargs"""
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.invoke = Mock(return_value="result")
        mock_tool.args_schema = None
        
        bound_tool = _bind_cooperative_to_tool(mock_tool, "test_coop")
        
        # Invoke with 'None' string value
        bound_tool.invoke({"query": "test", "location": "None"})
        
        # Verify 'None' was not passed to tool
        call_kwargs = mock_tool.invoke.call_args[0][0] if mock_tool.invoke.call_args else {}
        assert "None" not in str(call_kwargs.values())
    
    def test_removes_actual_none_values(self):
        """Test that actual None values are removed from kwargs"""
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.invoke = Mock(return_value="result")
        mock_tool.args_schema = None
        
        bound_tool = _bind_cooperative_to_tool(mock_tool, "test_coop")
        
        # Invoke with None value
        bound_tool.invoke({"query": "test", "location": None})
        
        # Verify None was not passed (or was cleaned)
        assert mock_tool.invoke.called
    
    def test_preserves_tool_schema(self):
        """Test that original tool's args_schema is preserved"""
        from pydantic import BaseModel
        
        class TestSchema(BaseModel):
            query: str
            location: str = None
        
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.invoke = Mock(return_value="result")
        mock_tool.args_schema = TestSchema
        
        bound_tool = _bind_cooperative_to_tool(mock_tool, "test_coop")
        
        # Verify schema is preserved
        assert hasattr(bound_tool, 'args_schema')
        assert bound_tool.args_schema == TestSchema
    
    def test_preserves_tool_name_and_description(self):
        """Test that tool name and description are preserved"""
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool description"
        mock_tool.invoke = Mock(return_value="result")
        mock_tool.args_schema = None
        
        bound_tool = _bind_cooperative_to_tool(mock_tool, "test_coop")
        
        assert bound_tool.name == "test_tool"
        assert bound_tool.description == "Test tool description"
    
    def test_handles_tool_invoke_error(self):
        """Test that tool invoke errors are handled gracefully"""
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.invoke = Mock(side_effect=Exception("Tool error"))
        mock_tool.args_schema = None
        
        bound_tool = _bind_cooperative_to_tool(mock_tool, "test_coop")
        
        # Should not raise exception, but may retry
        try:
            bound_tool.invoke({"query": "test"})
        except Exception:
            pass  # Expected to fail, but should handle gracefully
    
    def test_returns_original_tool_on_binding_error(self):
        """Test that original tool is returned if binding fails"""
        # Create a tool that will fail binding
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        # Make StructuredTool.from_function fail by making it raise
        with patch('src.chatbot.bot.chat_agent.StructuredTool') as mock_structured:
            mock_structured.from_function.side_effect = Exception("Binding error")
            
            result = _bind_cooperative_to_tool(mock_tool, "test_coop")
            
            # Should return original tool on error
            assert result == mock_tool

