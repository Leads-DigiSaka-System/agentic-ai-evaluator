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
    
    # Clean up excessive newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    
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
        agent_input = {
            "input": message,
            "chat_history": chat_history  # Add chat history to input
        }
        
        # Invoke agent
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
        
        # Fallback: try to extract from intermediate_steps if output is empty
        if not response_text and "intermediate_steps" in result:
            logger.debug("Response text is empty, checking intermediate_steps...")
            for step in reversed(result["intermediate_steps"]):
                if len(step) >= 2:
                    observation = step[1]
                    if isinstance(observation, str) and observation:
                        logger.debug(f"Found response in intermediate_steps: {observation[:100]}...")
                        response_text = observation
                        break
        
        # Extract tools used from intermediate_steps
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
        
        if not tools_used:
            logger.warning(f"⚠️ No tools were called for query: {message[:100]}...")
            logger.warning(f"Agent output: {response_text[:200] if response_text else 'EMPTY'}...")
            logger.warning(f"⚠️ This should not happen - agent MUST use tools for data queries!")
            
            # Try to force tool usage by re-invoking with explicit instruction
            if "intermediate_steps" not in result or len(result.get("intermediate_steps", [])) == 0:
                logger.info("🔄 Attempting to force tool usage with explicit instruction...")
                forced_message = f"MUST USE TOOLS: {message}\n\nIMPORTANT: You MUST call a search tool (search_analysis_tool, search_by_location_tool, etc.) to answer this question. You cannot answer without using tools."
                try:
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
                        logger.error("❌ Forced tool usage also failed - agent is not recognizing tools")
                except Exception as e:
                    logger.error(f"Error during forced tool usage: {e}")
        
        # Clean and convert technical responses to conversational
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
            "sources": []
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