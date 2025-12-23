"""
Chat Agent for Agricultural Data Queries

Uses LangChain's standard agent creation (create_openai_tools_agent) 
for reliable tool-based conversations with agricultural data.

Features:
- Tool-based agent with 16 agricultural data tools
- Cooperative-based data isolation
- OpenRouter LLM integration (Llama 3.3 70B Instruct)
- Conversation memory support
- Langfuse observability integration
"""
from typing import List, Optional, Dict, Any
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool

from src.utils.config import OPENROUTER_MODEL
from src.utils.openrouter_helper import create_openrouter_llm, is_openrouter_configured
from src.utils.clean_logger import get_clean_logger
from src.chatbot.prompts.system_prompt import get_chat_agent_system_prompt
from src.utils.llm_helper import get_langfuse_handler
from src.chatbot.memory.conversation_store import generate_thread_id

# Import all available tools
from src.chatbot.tools import (
    # Search tools (10)
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
        List of all LangChain tools
    """
    return [
        # Search tools (10)
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
        # List tools (3)
        list_reports_tool,
        get_stats_tool,
        get_report_by_id_tool,
        # Analysis tools (3)
        compare_products_tool,
        generate_summary_tool,
        get_trends_tool
    ]


def create_chat_agent(cooperative: str) -> AgentExecutor:
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
    
    if not is_openrouter_configured():
        raise ValueError(
            "OPENROUTER_API_KEY is not configured. "
            "Check OPENROUTER_API_KEY in .env file"
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
    
    openrouter_llm = create_openrouter_llm(
        model=OPENROUTER_MODEL,
        temperature=0.7,
        max_tokens=None,
        callbacks=callbacks if callbacks else None
    )
    
    if not openrouter_llm:
        raise ValueError(
            "Failed to create OpenRouter LLM. "
            "Check OPENROUTER_API_KEY configuration."
        )
    
    logger.info(f"🚀 OpenRouter LLM configured: {OPENROUTER_MODEL}")
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create agent using create_openai_tools_agent (direct, no try-except)
    agent = create_openai_tools_agent(
        llm=openrouter_llm,
        tools=bound_tools,
        prompt=prompt
    )
    
    # Create agent executor with proper configuration
    agent_executor = AgentExecutor(
        agent=agent,
        tools=bound_tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=15,
        max_execution_time=300,
        return_intermediate_steps=True,
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
        result = agent.invoke(agent_input)
        
        # Extract response from result
        response_text = result.get("output", "")
        
        # Fallback: try to extract from intermediate_steps if output is empty
        if not response_text and "intermediate_steps" in result:
            for step in reversed(result["intermediate_steps"]):
                if len(step) >= 2:
                    observation = step[1]
                    if isinstance(observation, str) and observation:
                        response_text = observation
                        break
        
        # Extract tools used from intermediate_steps
        tools_used = []
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if len(step) > 0:
                    action = step[0]
                    if hasattr(action, 'tool'):
                        tool_name = action.tool
                    elif isinstance(action, dict):
                        tool_name = action.get('tool', '')
                    else:
                        tool_name = str(action)
                    
                    if tool_name and tool_name not in tools_used:
                        tools_used.append(tool_name)
        
        # Validate response
        if (not response_text or 
            response_text.strip().lower() in ["none", "null", "error"] or 
            len(response_text.strip()) < 10):
            logger.warning(f"Agent returned empty or invalid response: {response_text}")
            response_text = (
                "I'm sorry, I couldn't generate a meaningful response. "
                "Please try again or rephrase your question."
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
