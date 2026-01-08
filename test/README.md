# Test Suite for Agentic AI Evaluator

## Overview

This directory contains unit tests for the chatbot module. Tests are written using `pytest`.

## Test Structure

```
test/
├── __init__.py
├── conftest.py              # Pytest configuration and fixtures
├── test_simple.py           # Simple tests (no dependencies)
└── test_chatbot/
    ├── __init__.py
    ├── test_chat_agent.py          # Tests for chat_agent.py
    ├── test_conversation_store.py  # Tests for conversation_store.py
    └── test_postgres_memory.py     # Tests for postgres_memory.py
```

## Running Tests

### Run All Tests
```bash
pytest test/
```

### Run Specific Test File
```bash
pytest test/test_chatbot/test_chat_agent.py
```

### Run Specific Test Class
```bash
pytest test/test_chatbot/test_chat_agent.py::TestCleanAgentResponse
```

### Run Specific Test Function
```bash
pytest test/test_chatbot/test_chat_agent.py::TestCleanAgentResponse::test_empty_string
```

### Run with Verbose Output
```bash
pytest test/ -v
```

### Run with Coverage
```bash
pytest test/ --cov=src --cov-report=html
```

## Test Coverage

### Current Tests

1. **test_chat_agent.py**
   - `_clean_agent_response()` - 11 tests
     - Empty string handling
     - Markdown removal
     - "No Results Found" conversion
     - Whitespace cleanup
   - `_bind_cooperative_to_tool()` - 7 tests
     - Cooperative injection
     - None value cleanup
     - Schema preservation
     - Error handling

2. **test_conversation_store.py**
   - `generate_thread_id()` - 6 tests
     - Thread ID format
     - Duplicate prefix prevention
     - Session ID generation

3. **test_postgres_memory.py**
   - `PostgresConversationMemory` - 5 tests
     - Memory loading
     - Connection error handling
     - Message limit enforcement

## Requirements

To run the full test suite, ensure all dependencies are installed:

```bash
# Install dependencies
uv sync
# or
pip install -r requirements.txt
```

## Note on Dependencies

Some tests require mocking external dependencies (PostgreSQL, LLM APIs, etc.). The test files include mocking setup, but you may need to adjust based on your environment.

## Future Improvements

- [ ] Add integration tests
- [ ] Add API endpoint tests
- [ ] Add performance tests
- [ ] Increase test coverage to 70%+

