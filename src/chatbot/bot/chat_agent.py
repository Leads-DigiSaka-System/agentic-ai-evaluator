"""
Chat Agent for Agricultural Data Queries

Uses LangChain's standard agent creation (create_openai_tools_agent) 
for reliable tool-based conversations with agricultural data.

Features:
- Tool-based agent with 27 agricultural data tools (11 basic search + 16 advanced search + 3 list + 3 analysis)
- Cooperative-based data isolation
- OpenRouter LLM integration (Llama 3.3 70B Instruct)
- Conversation memory support
- Langfuse observability integration
"""
from typing import List, Optional, Dict, Any
import re
from datetime import datetime, timedelta
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool

from src.utils.config import OPENROUTER_MODEL, GEMINI_MODEL, MAX_CONTEXT_MESSAGES
from src.utils.openrouter_helper import create_openrouter_llm, is_openrouter_configured
from src.utils.clean_logger import get_clean_logger
from src.chatbot.prompts.system_prompt import get_chat_agent_system_prompt
from src.utils.llm_helper import get_langfuse_handler
from src.chatbot.memory.conversation_store import generate_thread_id
from src.chatbot.memory.postgres_memory import PostgresConversationMemory
from src.utils.llm_factory import create_llm_for_agent, get_available_providers
from src.utils.gemini_helper import create_gemini_llm, is_gemini_configured
from src.utils.retry_helper import retry_llm_call

# Import all available tools
from src.chatbot.tools import (
    # Basic search tools (11)
    search_analysis_tool,
    search_by_product_tool,
    search_by_location_tool,
    search_by_crop_tool,
    search_by_cooperator_tool,
    search_by_season_tool,
    search_by_improvement_range_tool,
    search_by_sentiment_tool,
    search_by_product_category_tool,
    search_by_performance_significance_tool,
    search_by_applicant_tool,
    # Advanced search tools (16)
    search_by_form_type_tool,
    search_by_date_range_tool,
    search_by_metric_type_tool,
    search_by_confidence_level_tool,
    search_by_data_quality_tool,
    search_by_control_product_tool,
    search_by_speed_of_action_tool,
    search_by_yield_status_tool,
    search_by_yield_improvement_range_tool,
    search_by_measurement_intervals_tool,
    search_by_metrics_detected_tool,
    search_by_risk_factors_tool,
    search_by_opportunities_tool,
    search_by_recommendations_tool,
    search_by_key_observation_tool,
    search_by_scale_info_tool,
    # List tools (3)
    list_reports_tool,
    get_stats_tool,
    get_report_by_id_tool,
    # Analysis tools (3)
    compare_products_tool,
    generate_summary_tool,
    get_trends_tool
)

logger = get_clean_logger(__name__)

# Configuration: Limit number of messages used for context
# This prevents token limit issues and keeps context relevant
# Last 10 messages = 5 conversation turns (user + assistant pairs) - Very short context
# Value is now loaded from config.py (MAX_CONTEXT_MESSAGES env var, default: 10)


def _extract_clarification_questions(response_text: str) -> List[str]:
    """
    Extract clarification questions from agent response.
    
    This is used ONLY for extracting questions to return to frontend.
    We do NOT use this to determine if we should force tools - we trust the LLM.
    
    Args:
        response_text: Agent's response text
    
    Returns:
        List of clarification questions found in response (max 2-3)
    """
    if not response_text:
        return []
    
    questions = []
    
    # First, remove quoted example questions (they're examples, not actual clarification questions)
    # Pattern: "Pwede niyo pong itanong \"Question?\" o \"Question?\""
    # We want to extract the main clarification question, not the examples
    text_without_examples = re.sub(
        r'Pwede niyo pong itanong\s+["\']([^"\']+\?)["\']\s*(?:o\s+["\']([^"\']+\?)["\'])?',
        '',
        response_text,
        flags=re.IGNORECASE
    )
    
    # Pattern 1: Main clarification questions (the ones the agent is actually asking)
    # These typically start with clarification keywords and are NOT in quotes
    clarification_patterns = [
        r'(Ano pong[^?]+\?)',  # "Ano pong specific na..."
        r'(Pwede niyo po bang[^?]+\?)',  # "Pwede niyo po bang..."
        r'(Gusto niyo pong[^?]+\?)',  # "Gusto niyo pong..."
        r'(Mayroon kaming[^?]+\?)',  # "Mayroon kaming..."
    ]
    
    # Extract from the text without examples first
    for pattern in clarification_patterns:
        matches = re.findall(pattern, text_without_examples, re.IGNORECASE)
        for match in matches:
            question = match.strip()
            # Skip if it's in quotes (likely an example)
            if not (question.startswith('"') or question.startswith("'")):
                if question and question not in questions:
                    questions.append(question)
    
    # Pattern 2: If no main clarification found, look for questions in first part of response
    # (clarification questions usually come first, before examples)
    if not questions:
        # Get first 200 characters (where clarification usually appears)
        first_part = text_without_examples[:200] if len(text_without_examples) > 200 else text_without_examples
        question_sentences = re.findall(r'([^.!?]*\?)', first_part)
        
        for q in question_sentences:
            q = q.strip()
            # Filter for clarification-like questions
            clarification_keywords = ['specific', 'gusto niyo pong', 'ano pong', 'pwede niyo po bang']
            is_clarification = any(keyword in q.lower() for keyword in clarification_keywords)
            
            # Skip quoted examples and very short questions
            if is_clarification and len(q) > 10 and not (q.startswith('"') or q.startswith("'")):
                if q and q not in questions:
                    questions.append(q)
    
    # Clean questions: remove quotes, normalize
    cleaned_questions = []
    for q in questions[:3]:  # Limit to 3
        q = q.strip()
        # Remove surrounding quotes if present
        q = q.strip('"\'')
        # Remove trailing punctuation that's not a question mark
        if q and not q.endswith('?'):
            q = q.rstrip('.,;:') + '?'
        if q and len(q) > 5:  # Minimum length
            cleaned_questions.append(q)
    
    return cleaned_questions


def _extract_follow_up_questions(response_text: str) -> List[str]:
    """
    Extract follow-up question suggestions from agent response.
    
    The agent naturally suggests follow-up questions in its response. This function
    intelligently extracts them from various natural language patterns.
    
    Follow-up questions are different from clarification questions:
    - Clarification: Asked when query is ambiguous (before tools)
    - Follow-up: Suggested after providing answer (to guide next steps)
    
    The agent may suggest follow-ups in natural ways like:
    - "Kung gusto niyo pong makita ang performance, pwede niyo pong itanong 'Ano ang performance?'"
    - "Pwede niyo rin pong itanong 'Paano po ito ikumpara sa ibang products?'"
    - Or simply include questions at the end: "Ano ang best performing product?"
    
    Args:
        response_text: Agent's complete response text
    
    Returns:
        List of follow-up questions (max 3), empty if none found
    """
    if not response_text:
        return []
    
    questions = []
    
    # Pattern 1: Look for explicit "FOLLOW-UP QUESTIONS:" section (backward compatibility)
    # Some agents might still use this format
    follow_up_section_pattern = r'(?i)\*\*FOLLOW-UP QUESTIONS?:\*\*\s*\n?(.*?)(?=\n\n|\n\*\*|$)'
    section_match = re.search(follow_up_section_pattern, response_text, re.DOTALL | re.IGNORECASE)
    
    if section_match:
        section_text = section_match.group(1)
        numbered_pattern = r'(?:^|\n)\s*\d+[.)]\s*([^\n]+?)(?=\n\s*\d+[.)]|\n\n|$)'
        numbered_matches = re.findall(numbered_pattern, section_text, re.MULTILINE)
        
        for match in numbered_matches:
            question = match.strip()
            if question and not question.endswith('?'):
                question = question.rstrip('.,;:')
            if question:
                questions.append(question)
    
    # Pattern 2: Extract from natural language suggestions
    # Look for patterns like "pwede niyo pong itanong '...'" or "kung gusto niyo pong... itanong '...'"
    if len(questions) < 3:
        # Pattern: "pwede niyo pong itanong 'Question?'" or "itanong 'Question?'"
        natural_patterns = [
            r"pwede niyo pong itanong ['\"]([^'\"]+\?)['\"]",  # "pwede niyo pong itanong 'Question?'"
            r"kung gusto niyo pong[^?]*itanong ['\"]([^'\"]+\?)['\"]",  # "kung gusto niyo pong... itanong 'Question?'"
            r"pwede niyo rin pong itanong ['\"]([^'\"]+\?)['\"]",  # "pwede niyo rin pong itanong 'Question?'"
            r"itanong ['\"]([^'\"]+\?)['\"]",  # "itanong 'Question?'"
        ]
        
        for pattern in natural_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for match in matches:
                question = match.strip()
                if question and question not in questions:
                    questions.append(question)
    
    # Pattern 3: Extract questions from the last portion of response (natural follow-ups)
    # Follow-up questions typically appear at the end after the main answer
    if len(questions) < 3:
        response_length = len(response_text)
        # Look at last 40% of response (where follow-ups usually appear)
        last_section = response_text[int(response_length * 0.6):] if response_length > 100 else response_text
        
        # Find all questions in the last section
        question_sentences = re.findall(r'([^.!?]*\?)', last_section)
        
        for q in question_sentences:
            q = q.strip()
            if not q or len(q) < 10:  # Skip very short questions
                continue
            
            # Filter out clarification questions
            clarification_keywords = [
                'specific', 'gusto niyo pong', 'ano pong specific', 
                'pwede niyo po bang', 'clarification', 'ano pong'
            ]
            is_clarification = any(keyword in q.lower() for keyword in clarification_keywords)
            
            if is_clarification:
                continue
            
            # Identify follow-up questions by keywords or context
            follow_up_indicators = [
                'gusto ko pong', 'paano po', 'ano ang', 'kailan po', 
                'mayroon ba', 'ikumpara', 'performance', 'ibang', 
                'saan pa', 'best', 'compare', 'highest', 'lowest'
            ]
            is_follow_up = any(indicator in q.lower() for indicator in follow_up_indicators)
            
            # Also consider questions that are longer (likely follow-ups, not clarifications)
            if is_follow_up or (len(q) > 20 and '?' in q):
                if q not in questions:
                    questions.append(q)
    
    # Clean and normalize questions
    cleaned_questions = []
    for q in questions[:3]:  # Limit to 3
        q = q.strip()
        # Remove quotes if present
        q = q.strip("'\"")
        # Ensure it ends with ?
        if q and not q.endswith('?'):
            q = q.rstrip('.,;:') + '?'
        if q and len(q) > 5:  # Minimum length check
            cleaned_questions.append(q)
    
    return cleaned_questions


def _clean_agent_response(response_text: str) -> str:
    """
    Clean and convert technical/markdown tool outputs to conversational responses.
    
    Args:
        response_text: Raw response text from agent
    
    Returns:
        Cleaned, conversational response text
    """
    if not response_text:
        return response_text
    
    # Remove markdown headers and convert to plain text
    # Remove markdown headers (##, ###, etc.)
    cleaned = re.sub(r'^#+\s*', '', response_text, flags=re.MULTILINE)
    
    # Convert "No Results Found" type messages to conversational
    if re.search(r'##\s*No\s+Results?\s+Found', response_text, re.IGNORECASE):
        # Extract query if present
        query_match = re.search(r'query:\s*(.+)', response_text, re.IGNORECASE)
        if query_match:
            query = query_match.group(1).strip()
            # Try to extract location/product from query
            if 'location:' in query.lower():
                location = query.split(':')[-1].strip()
                return f"Wala po akong nahanap na trials o demos sa {location}. Baka wala pa pong na-upload na reports para sa lugar na iyan, o maaaring iba ang spelling ng location. Pwede niyo po bang subukan ulit o magtanong tungkol sa ibang lugar?"
            elif 'product:' in query.lower():
                product = query.split(':')[-1].strip()
                return f"Wala po akong nahanap na trials o demos para sa {product}. Baka wala pa pong na-upload na reports para sa produktong iyan. Pwede niyo po bang subukan ulit o magtanong tungkol sa ibang produkto?"
        return "Wala po akong nahanap na results para sa inyong query. Pwede niyo po bang subukan ulit o magtanong ng ibang tanong?"
    
    # Remove technical prefixes like "No results found for query:"
    cleaned = re.sub(r'No\s+results?\s+found\s+for\s+query:\s*', '', cleaned, flags=re.IGNORECASE)
    
    # Remove markdown formatting but keep content
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)  # Remove bold
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)  # Remove italic
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)  # Remove code blocks
    
    # Remove quoted example questions from clarification responses
    # Pattern: "Pwede niyo pong itanong \"Question?\" o \"Question?\""
    # These are examples, not part of the main clarification question
    cleaned = re.sub(
        r'\s*Pwede niyo pong itanong\s+["\']([^"\']+\?)["\']\s*(?:o\s+["\']([^"\']+\?)["\'])?[^.]*\.?',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    
    # Also remove patterns like "pwede niyo pong itanong 'Question?'" or "itanong 'Question?'"
    cleaned = re.sub(
        r'\s*(?:pwede niyo pong|pwede niyo rin pong|kung gusto niyo pong)\s+itanong\s+["\']([^"\']+\?)["\']\s*(?:o\s+["\']([^"\']+\?)["\'])?[^.]*\.?',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    
    # Remove explicit "FOLLOW-UP QUESTIONS:" section if present (old format)
    # But keep naturally embedded questions - they're part of the conversation flow
    # We extract them separately for frontend, but they can also stay in the response
    cleaned = re.sub(
        r'(?i)\*\*FOLLOW-UP QUESTIONS?:\*\*\s*\n?.*$',
        '',
        cleaned,
        flags=re.DOTALL | re.MULTILINE
    )
    
    # Clean up excessive newlines and spaces
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'\s{3,}', ' ', cleaned)  # Remove excessive spaces
    
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    
    # Remove trailing periods if the response ends with a question mark
    if cleaned.endswith('?'):
        cleaned = cleaned.rstrip('.')
    
    return cleaned


def _bind_cooperative_to_tool(tool, cooperative: str) -> StructuredTool:
    """
    Bind cooperative parameter to a tool for data isolation.
    
    Args:
        tool: LangChain tool to bind
        cooperative: Cooperative ID to inject
    
    Returns:
        New tool with cooperative parameter pre-filled
    """
    try:
        # Simple wrapper that injects cooperative - tools are called with kwargs only
        def tool_wrapper(**kwargs):
            """Wrapper that automatically injects cooperative parameter"""
            # Clean up 'None' string values - remove them entirely instead of setting to None
            # This avoids Pydantic validation errors for str = None parameters
            cleaned_kwargs = {}
            for key, value in kwargs.items():
                # Skip 'None' string values entirely (don't pass them to tool)
                if isinstance(value, str) and (value.lower() == 'none' or value.lower() == 'null'):
                    continue  # Don't include this parameter
                # Also skip actual None values for optional parameters
                elif value is None:
                    continue  # Don't include None values
                else:
                    cleaned_kwargs[key] = value
            
            # Inject cooperative if not present or None
            if 'cooperative' not in cleaned_kwargs or cleaned_kwargs['cooperative'] is None:
                cleaned_kwargs['cooperative'] = cooperative
            
            # Log non-None filters for debugging
            active_filters = {k: v for k, v in cleaned_kwargs.items() if v is not None and k != 'cooperative'}
            if active_filters:
                logger.debug(f"🔍 Tool {tool.name} called with active filters: {active_filters}")
            
            try:
                return tool.invoke(cleaned_kwargs)
            except Exception as e:
                logger.debug(f"Tool invoke failed, retrying with explicit cooperative: {e}")
                return tool.invoke({**cleaned_kwargs, 'cooperative': cooperative})
        
        # Create new tool with bound cooperative - preserve original schema
        bound_tool = StructuredTool.from_function(
            func=tool_wrapper,
            name=tool.name,
            description=tool.description
        )
        
        # CRITICAL: Preserve original tool's schema completely
        if hasattr(tool, 'args_schema'):
            bound_tool.args_schema = tool.args_schema
        
        # Note: input_schema is read-only, so we don't try to set it
        # The schema is automatically preserved by StructuredTool.from_function
        
        logger.debug(f"✅ Bound cooperative '{cooperative}' to tool '{tool.name}'")
        return bound_tool
    except Exception as e:
        import traceback
        logger.warning(f"Error binding cooperative to tool {tool.name}: {e}")
        logger.debug(traceback.format_exc())
        # Return original tool if binding fails
        return tool


def _get_all_tools() -> List:
    """
    Get all available tools for the chat agent.
    
    Returns:
        List of all LangChain tools (27 total: 11 basic search + 16 advanced search + 3 list + 3 analysis)
    """
    return [
        # Basic search tools (11)
        search_analysis_tool,
        search_by_product_tool,
        search_by_location_tool,
        search_by_crop_tool,
        search_by_cooperator_tool,
        search_by_season_tool,
        search_by_improvement_range_tool,
        search_by_sentiment_tool,
        search_by_product_category_tool,
        search_by_performance_significance_tool,
        search_by_applicant_tool,
        # Advanced search tools (16)
        search_by_form_type_tool,
        search_by_date_range_tool,
        search_by_metric_type_tool,
        search_by_confidence_level_tool,
        search_by_data_quality_tool,
        search_by_control_product_tool,
        search_by_speed_of_action_tool,
        search_by_yield_status_tool,
        search_by_yield_improvement_range_tool,
        search_by_measurement_intervals_tool,
        search_by_metrics_detected_tool,
        search_by_risk_factors_tool,
        search_by_opportunities_tool,
        search_by_recommendations_tool,
        search_by_key_observation_tool,
        search_by_scale_info_tool,
        # List tools (3)
        list_reports_tool,
        get_stats_tool,
        get_report_by_id_tool,
        # Analysis tools (3)
        compare_products_tool,
        generate_summary_tool,
        get_trends_tool
    ]


def create_chat_agent(
    cooperative: str,
    model_provider: str = "openrouter"  # Options: "openrouter" or "gemini"
) -> AgentExecutor:
    """
    Create a LangChain agent for chat with all tools and cooperative context.
    
    Uses standard LangChain agent creation (create_openai_tools_agent)
    which uses the modern tools API.
    
    Args:
        cooperative: Cooperative ID for data isolation (required)
    
    Returns:
        AgentExecutor instance configured with all tools
    
    Raises:
        ValueError: If cooperative is missing or OpenRouter is not configured
    """
    # Validation
    if not cooperative:
        raise ValueError("Cooperative ID is required for chat agent")
    
    provider_lower = model_provider.lower()
    if provider_lower == "gemini":
        from src.utils.gemini_helper import is_gemini_configured
        if not is_gemini_configured():
            raise ValueError(
                "GEMINI_APIKEY is not configured. "
                "Check GEMINI_APIKEY in .env file"
            )
    elif provider_lower == "openrouter":
        if not is_openrouter_configured():
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. "
                "Check OPENROUTER_API_KEY in .env file"
            )
    else:
        raise ValueError(
            f"Unsupported provider: {model_provider}. "
            "Supported providers: 'openrouter', 'gemini'"
        )
    
    logger.info(f"Creating chat agent for cooperative: {cooperative}")
    
    # Get system prompt
    system_prompt = get_chat_agent_system_prompt()
    
    # Get all tools and bind cooperative
    all_tools = _get_all_tools()
    bound_tools = []
    
    for tool in all_tools:
        try:
            bound_tool = _bind_cooperative_to_tool(tool, cooperative)
            bound_tools.append(bound_tool)
        except Exception as e:
            logger.warning(f"Could not bind cooperative to tool {tool.name}: {e}")
            bound_tools.append(tool)
    
    logger.info(f"Created {len(bound_tools)} tools with cooperative context")
    
    # Create OpenRouter LLM instance
    callbacks = []
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler:
        callbacks.append(langfuse_handler)
        logger.debug("Chat agent LLM initialized with Langfuse tracking")
    
    # Use factory to create LLM (supports both OpenRouter and Gemini)
    llm = create_llm_for_agent(
        provider=model_provider,
        temperature=0.7,
        max_tokens=None
    )
    
    if not llm:
        provider_key = "GEMINI_APIKEY" if provider_lower == "gemini" else "OPENROUTER_API_KEY"
        raise ValueError(
            f"Failed to create {model_provider} LLM. "
            f"Check {provider_key} configuration."
        )
    
    # Get model name for logging
    provider_model = GEMINI_MODEL if provider_lower == "gemini" else OPENROUTER_MODEL
    logger.info(f"🚀 {model_provider.capitalize()} LLM configured: {provider_model}")
    
    # Create prompt template with chat_history placeholder for memory
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),  # For conversation memory
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Verify tools before creating agent
    if not bound_tools:
        raise ValueError("No tools available for agent creation")
    
    logger.info(f"📋 Creating agent with {len(bound_tools)} tools")
    tool_names = [t.name for t in bound_tools[:5]]
    logger.debug(f"Sample tools: {tool_names}...")
    
    # Create agent using create_openai_tools_agent (direct, no try-except)
    agent = create_openai_tools_agent(
        llm=llm,
        tools=bound_tools,
        prompt=prompt
    )
    
    # Verify agent was created with tools
    if hasattr(agent, 'tools'):
        logger.debug(f"✅ Agent created with {len(agent.tools)} tools")
    else:
        logger.warning("⚠️ Agent created but tools attribute not found")
    
    # Create agent executor with proper configuration
    agent_executor = AgentExecutor(
        agent=agent,
        tools=bound_tools,  # Also pass tools to executor for redundancy
        verbose=True,  # Enable verbose mode for debugging
        handle_parsing_errors=True,
        max_iterations=15,
        max_execution_time=300,
        return_intermediate_steps=True,
        early_stopping_method="force",  # Force agent to use tools
    )
    
    # Store system prompt for reference
    agent_executor._system_prompt = system_prompt
    
    logger.info(
        f"✅ Chat agent created successfully with {len(bound_tools)} tools "
        f"using {OPENROUTER_MODEL}"
    )
    return agent_executor

def invoke_agent(
    agent: AgentExecutor,
    message: str,
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    cooperative: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Invoke the chat agent with a user message.
    
    Args:
        agent: AgentExecutor instance
        message: User's message/query
        session_id: Optional session ID for conversation continuity
        thread_id: Optional thread ID for conversation memory
        cooperative: Optional cooperative ID (for logging)
        user_id: Optional user ID (for logging)
    
    Returns:
        Dictionary with:
        - response: Agent's response text
        - session_id: Session ID for this conversation
        - tools_used: List of tool names used
        - metadata: Additional metadata (model, cooperative)
        - sources: List of data sources (empty for now)
    """
    try:
        # Generate thread_id if not provided
        if not thread_id and cooperative and user_id and session_id:
            thread_id = generate_thread_id(
                cooperative,
                user_id,
                session_id
            )
        
        # Initialize memory for this thread
        memory = None
        chat_history = []
        session_expired = False
        
        if thread_id:
            try:
                logger.info(f"🔍 Loading memory for thread: {thread_id}")
                # Create PostgreSQL-backed memory
                memory = PostgresConversationMemory(
                    thread_id=thread_id,
                    return_messages=True,  # Return as messages for prompt
                    input_key="input",
                    output_key="output",
                    memory_key="chat_history"  # Explicitly set memory key
                )
                
                # Check if session expired (memory._load_from_postgres returns session_expired flag)
                # The memory is loaded automatically in __init__, so we check the result
                if hasattr(memory, '_loaded') and not memory._loaded:
                    # If memory wasn't loaded, check if it's because session expired
                    # We'll detect this by checking if chat_history is empty after initialization
                    if not hasattr(memory, 'chat_memory') or not memory.chat_memory.messages:
                        # Check if session expired by querying directly
                        from src.utils.postgres_pool import get_postgres_connection, return_connection
                        from src.utils.config import SESSION_TIMEOUT_MINUTES
                        conn = get_postgres_connection()
                        if conn:
                            try:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    SELECT last_message_at
                                    FROM conversation_threads
                                    WHERE thread_id = %s
                                """, (thread_id,))
                                thread_info = cursor.fetchone()
                                if thread_info and thread_info[0]:
                                    last_message_at = thread_info[0]
                                    if isinstance(last_message_at, datetime):
                                        if last_message_at.tzinfo is not None:
                                            last_message_at = last_message_at.replace(tzinfo=None)
                                    timeout_threshold = datetime.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
                                    if last_message_at < timeout_threshold:
                                        session_expired = True
                                        logger.info(f"⏰ Session expired detected for thread {thread_id}")
                                cursor.close()
                            except Exception as e:
                                logger.debug(f"Could not check session expiration: {e}")
                            finally:
                                return_connection(conn)
                
                # Load chat history from memory
                if hasattr(memory, 'chat_memory') and hasattr(memory.chat_memory, 'messages'):
                    all_messages = memory.chat_memory.messages
                    
                    # Limit to most recent messages to prevent token limit issues
                    if len(all_messages) > MAX_CONTEXT_MESSAGES:
                        chat_history = all_messages[-MAX_CONTEXT_MESSAGES:]
                        logger.info(f"✅ Loaded {len(all_messages)} total messages, using last {len(chat_history)} for context (thread: {thread_id})")
                    else:
                        chat_history = all_messages
                        logger.info(f"✅ Loaded {len(chat_history)} messages from chat_memory for thread: {thread_id}")
                    
                    if chat_history:
                        for i, msg in enumerate(chat_history[-4:], 1):
                            msg_type = type(msg).__name__
                            content = msg.content[:80] if hasattr(msg, 'content') else str(msg)[:80]
                            logger.debug(f"   Recent message {i}: {msg_type} - {content}...")
                else:
                    # Try loading from memory variables
                    memory_vars = memory.load_memory_variables({})
                    all_history = memory_vars.get('chat_history', memory_vars.get('history', []))
                    
                    # Limit to most recent messages to prevent token limit issues
                    if len(all_history) > MAX_CONTEXT_MESSAGES:
                        chat_history = all_history[-MAX_CONTEXT_MESSAGES:]
                        logger.info(f"✅ Loaded {len(all_history)} total messages, using last {len(chat_history)} for context (thread: {thread_id})")
                    else:
                        chat_history = all_history
                        logger.info(f"✅ Loaded {len(chat_history)} messages from memory variables for thread: {thread_id}")
                
                if not chat_history:
                    logger.warning(f"⚠️ No chat history found for thread: {thread_id} (this might be a new conversation)")
            except Exception as e:
                import traceback
                logger.warning(f"Failed to load memory for thread {thread_id}: {e}")
                logger.debug(traceback.format_exc())
                logger.info("Continuing without memory (conversation will not have context)")
        
        # Prepare input for agent with chat history
        # NOTE: We trust the LLM to determine if query is ambiguous based on system prompt
        # The LLM will handle clarification requests according to the system prompt instructions
        agent_input = {
            "input": message,
            "chat_history": chat_history  # Add chat history to input
        }
        
        # Invoke agent - LLM will determine if clarification is needed based on system prompt
        logger.info(f"🔍 Invoking agent with message: {message[:100]}...")
        logger.debug(f"Agent input keys: {list(agent_input.keys())}")
        logger.debug(f"Chat history length: {len(chat_history) if chat_history else 0}")
        
        # Log available tools for debugging
        if hasattr(agent, 'tools'):
            logger.debug(f"Agent has {len(agent.tools)} tools available")
            tool_names = [t.name for t in agent.tools[:5]]  # Log first 5
            logger.debug(f"Sample tool names: {tool_names}")
        
        # Invoke agent with retry logic for LLM API calls
        # This handles transient API failures (network issues, rate limits, etc.)
        try:
            result = retry_llm_call(
                agent.invoke,
                agent_input,
                max_attempts=3  # Use config default or override
            )
        except Exception as e:
            # If retry fails, log and re-raise
            logger.error(f"Agent invocation failed after retries: {str(e)}")
            raise
        
        # Debug: Log full result structure
        logger.debug(f"Agent result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
        if "intermediate_steps" in result:
            logger.debug(f"Intermediate steps count: {len(result['intermediate_steps'])}")
            for i, step in enumerate(result["intermediate_steps"]):
                logger.debug(f"Step {i}: {type(step)}, length: {len(step) if isinstance(step, (list, tuple)) else 'N/A'}")
        
        # Extract response from result
        response_text = result.get("output", "")
        logger.debug(f"Initial response_text length: {len(response_text) if response_text else 0}")
        
        # Extract tools used from intermediate_steps FIRST (before checking for clarification)
        tools_used = []
        if "intermediate_steps" in result:
            logger.debug(f"Extracting tools from {len(result['intermediate_steps'])} intermediate steps...")
            for step in result["intermediate_steps"]:
                if len(step) > 0:
                    action = step[0]
                    if hasattr(action, 'tool'):
                        tool_name = action.tool
                        logger.debug(f"Found tool via .tool attribute: {tool_name}")
                    elif isinstance(action, dict):
                        tool_name = action.get('tool', '')
                        logger.debug(f"Found tool via dict: {tool_name}")
                    elif hasattr(action, 'tool_name'):
                        tool_name = action.tool_name
                        logger.debug(f"Found tool via .tool_name attribute: {tool_name}")
                    else:
                        tool_name = str(action)
                        logger.debug(f"Tool name from str(action): {tool_name[:50]}...")
                    
                    if tool_name and tool_name not in tools_used:
                        tools_used.append(tool_name)
                        logger.debug(f"Added tool to tools_used: {tool_name}")
        
        # Fallback: try to extract response from intermediate_steps if output is empty
        # This helps capture clarification responses that might not be in the output field
        if not response_text and "intermediate_steps" in result:
            logger.debug("Response text is empty, checking intermediate_steps for response...")
            for step in reversed(result["intermediate_steps"]):
                if len(step) >= 2:
                    observation = step[1]
                    if isinstance(observation, str) and observation:
                        # Check if this looks like a clarification (not a tool result)
                        if not any(tool_name.lower() in observation.lower() for tool_name in tools_used):
                            logger.debug(f"Found potential response in intermediate_steps: {observation[:100]}...")
                            response_text = observation
                            break
        
        # Trust the LLM's decision - if it provided a response (even without tools), trust it
        # The system prompt already instructs the LLM to ask for clarification when needed
        # We should NOT programmatically detect clarification - let the LLM handle it
        if not tools_used:
            if response_text and len(response_text.strip()) > 10:
                # LLM provided a response without tools - this could be:
                # 1. Clarification request (correct behavior for ambiguous queries)
                # 2. General conversation (correct behavior)
                # Trust the LLM's decision completely
                logger.info(f"✅ Agent provided response without tools: {response_text[:100]}... (trusting LLM decision)")
            elif not response_text or len(response_text.strip()) < 10:
                # Response is empty or too short - this might be an error
                # Only force tools if response is truly empty/invalid AND no intermediate steps
                logger.warning(f"⚠️ No tools called AND response is empty/invalid for query: {message[:100]}...")
                logger.warning(f"Agent output: {response_text[:200] if response_text else 'EMPTY'}...")
                
                # Only force tool usage if response is truly empty AND no intermediate steps
                # This is a last resort - the LLM should handle most cases via system prompt
                if "intermediate_steps" not in result or len(result.get("intermediate_steps", [])) == 0:
                    logger.info("🔄 Attempting to force tool usage with explicit instruction...")
                    forced_message = f"MUST USE TOOLS: {message}\n\nIMPORTANT: You MUST call a search tool (search_analysis_tool, search_by_location_tool, etc.) to answer this question. You cannot answer without using tools."
                    try:
                        # Call agent.invoke directly (not through retry_llm_call to avoid streaming issues)
                        # Agent.invoke() already handles retries internally via LangChain
                        forced_result = agent.invoke({
                            "input": forced_message,
                            "chat_history": chat_history
                        })
                        
                        if "intermediate_steps" in forced_result and len(forced_result["intermediate_steps"]) > 0:
                            logger.info("✅ Forced tool usage succeeded")
                            result = forced_result
                            response_text = forced_result.get("output", response_text)
                            # Re-extract tools_used
                            tools_used = []
                            for step in forced_result["intermediate_steps"]:
                                if len(step) > 0:
                                    action = step[0]
                                    if hasattr(action, 'tool'):
                                        tool_name = action.tool
                                    elif isinstance(action, dict):
                                        tool_name = action.get('tool', '')
                                    elif hasattr(action, 'tool_name'):
                                        tool_name = action.tool_name
                                    else:
                                        tool_name = str(action)
                                    if tool_name and tool_name not in tools_used:
                                        tools_used.append(tool_name)
                        else:
                            logger.warning("⚠️ Forced tool usage did not result in tool calls - agent may need clarification")
                    except Exception as e:
                        logger.error(f"Error during forced tool usage: {e}")
                        # If forced tool usage fails, don't break - use the original response
                        # This is better than crashing - the LLM's original response (even if empty) is better than an error
        
        # Extract clarification questions BEFORE cleaning (so we can parse the raw format)
        # This ensures we capture the full clarification question before cleaning removes examples
        clarification_questions = _extract_clarification_questions(response_text)
        
        # Extract follow-up questions BEFORE cleaning (so we can parse the raw format)
        # Follow-up questions are only extracted if tools were used (meaning we provided an answer)
        follow_up_questions = []
        if tools_used:  # Only suggest follow-ups after providing an answer
            follow_up_questions = _extract_follow_up_questions(response_text)
            if follow_up_questions:
                logger.info(f"✅ Extracted {len(follow_up_questions)} follow-up question suggestions")
        
        # Clean and convert technical responses to conversational
        # This will remove quoted example questions and follow-up sections from the main response
        response_text = _clean_agent_response(response_text)
        
        # Validate response
        if (not response_text or 
            response_text.strip().lower() in ["none", "null", "error"] or 
            len(response_text.strip()) < 10):
            logger.warning(f"Agent returned empty or invalid response: {response_text}")
            response_text = (
                "Pasensya na po, hindi ko po makabuo ng makabuluhang sagot. "
                "Pwede niyo po bang subukan ulit o ibahin ang inyong tanong?"
            )
        
        # Save conversation to memory
        if memory and thread_id:
            try:
                # Save context to PostgreSQL memory
                memory.save_context(
                    inputs={"input": message},
                    outputs={
                        "output": response_text,
                        "tools_used": tools_used,
                        "metadata": {
                            "cooperative": cooperative,
                            "user_id": user_id,
                            "session_id": session_id
                        }
                    }
                )
                logger.debug(f"💾 Saved conversation to PostgreSQL memory for thread: {thread_id}")
            except Exception as e:
                logger.warning(f"Failed to save conversation to memory: {e}")
        
        return {
            "response": response_text,
            "session_id": session_id or thread_id,
            "tools_used": tools_used,
            "metadata": {
                "model": OPENROUTER_MODEL,
                "cooperative": cooperative,
                "thread_id": thread_id
            },
            "sources": [],
            "clarification_questions": clarification_questions,
            "follow_up_questions": follow_up_questions,  # Add follow-up questions to response
            "session_expired": session_expired,
            "session_active": not session_expired
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Agent invocation failed: {str(e)}\n{traceback.format_exc()}")
        return {
            "response": (
                "I encountered an error processing your request. "
                "Please try again or rephrase your question."
            ),
            "error": str(e),
            "session_id": session_id,
            "tools_used": [],
            "metadata": {},
            "sources": []
        }