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

from src.utils.config import OPENROUTER_MODEL, GEMINI_MODEL
from src.utils.openrouter_helper import create_openrouter_llm, is_openrouter_configured
from src.utils.clean_logger import get_clean_logger
from src.chatbot.prompts.system_prompt import get_chat_agent_system_prompt
from src.utils.llm_helper import get_langfuse_handler
from src.chatbot.memory.conversation_store import generate_thread_id
from src.utils.llm_factory import create_llm_for_agent, get_available_providers
from src.utils.gemini_helper import create_gemini_llm, is_gemini_configured

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
        def tool_wrapper(**kwargs):
            """Wrapper that automatically injects cooperative parameter"""
            if 'cooperative' not in kwargs:
                kwargs['cooperative'] = cooperative
            try:
                return tool.invoke(kwargs)
            except Exception as e:
                logger.debug(f"Tool invoke failed, retrying with explicit cooperative: {e}")
                return tool.invoke({**kwargs, 'cooperative': cooperative})
        
        # Create new tool with bound cooperative
        bound_tool = StructuredTool.from_function(
            func=tool_wrapper,
            name=tool.name,
            description=tool.description
        )
        
        # Preserve original tool's schema if available
        if hasattr(tool, 'args_schema'):
            bound_tool.args_schema = tool.args_schema
        
        return bound_tool
    except Exception as e:
        logger.warning(f"Error binding cooperative to tool {tool.name}: {e}")
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
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create agent using create_openai_tools_agent (direct, no try-except)
    agent = create_openai_tools_agent(
        llm=llm,
        tools=bound_tools,
        prompt=prompt
    )
    
    # Create agent executor with proper configuration
    agent_executor = AgentExecutor(
        agent=agent,
        tools=bound_tools,
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
        if not thread_id and session_id and user_id:
            thread_id = generate_thread_id(
                cooperative or "default",
                user_id,
                session_id
            )
        
        # Prepare input for agent
        # AgentExecutor expects a dict with "input" key
        agent_input = {"input": message}
        
        # Invoke agent
        logger.debug(f"Invoking agent with message: {message[:100]}...")
        result = agent.invoke(agent_input)
        
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
            logger.warning(f"No tools were called for query: {message[:100]}...")
            logger.warning(f"Agent output: {response_text[:200] if response_text else 'EMPTY'}...")
        
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
        
        return {
            "response": response_text,
            "session_id": session_id or thread_id,
            "tools_used": tools_used,
            "metadata": {
                "model": OPENROUTER_MODEL,
                "cooperative": cooperative
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