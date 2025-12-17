from typing import List, Optional, Dict, Any
from deepagents import create_deep_agent
from langchain_groq import ChatGroq
from src.utils.config import GROQ_MODEL, GROQ_API_KEY
from src.utils.clean_logger import get_clean_logger
from src.chatbot.prompts.system_prompt import get_chat_agent_system_prompt
from src.utils.llm_helper import get_langfuse_handler
from src.chatbot.tools import (
    # Search tools
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
    # List tools
    list_reports_tool,
    get_stats_tool,
    get_report_by_id_tool,
    # Analysis tools
    compare_products_tool,
    generate_summary_tool,
    get_trends_tool
)

logger = get_clean_logger(__name__)


def create_chat_agent(cooperative: str) -> Any:
    """
    Create a Deep Agent for chat with all tools and cooperative context.
    
    Args:
        cooperative: Cooperative ID for data isolation (required)
    
    Returns:
        Deep Agent instance configured with all tools
    """
    if not cooperative:
        raise ValueError("Cooperative ID is required for chat agent")
    
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured. Check GROQ_API_KEY in .env file")
    
    logger.info(f"Creating chat agent for cooperative: {cooperative}")
    
    # Get system prompt
    system_prompt = get_chat_agent_system_prompt()
    
    # Get all tools
    # Note: Tools need cooperative parameter, but Deep Agents will handle passing it
    # We'll need to bind cooperative to tools or pass it via context
    all_tools = [
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
    
    # Create tools with cooperative bound
    # Since LangChain tools don't support partial binding directly,
    # we'll need to create wrapper functions or pass cooperative via tool context
    # For now, we'll create a wrapper that injects cooperative
    
    def bind_cooperative_to_tool(tool, coop: str):
        """Bind cooperative parameter to a tool"""
        from langchain_core.tools import StructuredTool
        
        # Get the original tool's function
        original_func = tool.func if hasattr(tool, 'func') else tool
        
        # Create wrapper that injects cooperative
        def tool_wrapper(**kwargs):
            kwargs['cooperative'] = coop
            return tool.invoke(kwargs)
        
        # Create new tool with bound cooperative
        return StructuredTool.from_function(
            func=tool_wrapper,
            name=tool.name,
            description=tool.description
        )
    
    # Bind cooperative to all tools
    bound_tools = []
    for tool in all_tools:
        try:
            bound_tool = bind_cooperative_to_tool(tool, cooperative)
            bound_tools.append(bound_tool)
        except Exception as e:
            logger.warning(f"Could not bind cooperative to tool {tool.name}: {str(e)}")
            # Fallback: use original tool (agent will need to pass cooperative)
            bound_tools.append(tool)
    
    logger.info(f"Created {len(bound_tools)} tools with cooperative context")
    
    # Create Groq LLM instance with Langfuse integration
    callbacks = []
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler:
        callbacks.append(langfuse_handler)
        logger.debug("Chat agent LLM initialized with Langfuse tracking")
    
    # Create ChatGroq instance with reasoning model support
    # For reasoning models like deepseek-r1, use reasoning_format="parsed"
    is_reasoning_model = "r1" in GROQ_MODEL.lower() or "reasoning" in GROQ_MODEL.lower()
    
    groq_llm_kwargs = {
        "model": GROQ_MODEL,
        "groq_api_key": GROQ_API_KEY,
        "temperature": 0,  # Use 0 for reasoning models
        "max_retries": 2,
        "callbacks": callbacks if callbacks else None
    }
    
    # Add reasoning_format for reasoning models
    if is_reasoning_model:
        groq_llm_kwargs["reasoning_format"] = "parsed"
        groq_llm_kwargs["max_tokens"] = None  # No limit for reasoning
        groq_llm_kwargs["timeout"] = None  # No timeout for reasoning
        logger.info(f"🧠 Reasoning model detected: {GROQ_MODEL}")
    else:
        groq_llm_kwargs["temperature"] = 0.7  # Balanced creativity for non-reasoning models
    
    groq_llm = ChatGroq(**groq_llm_kwargs)
    
    logger.info(f"🚀 Groq LLM configured: {GROQ_MODEL}")
    
    # Note: Deep Agents automatically includes file system tools and context management
    # We don't need to configure checkpoint here - it's handled via thread_id in invoke_agent
    # File system tools work automatically with default StateBackend
    
    try:
        # Deep Agents create_deep_agent signature:
        # Try different parameter names based on version
        # Some versions use 'instructions' instead of 'system_prompt'
        # Memory is handled via thread_id in invoke_agent
        try:
            # Try with system_prompt first (newer versions)
            agent = create_deep_agent(
                model=groq_llm,
                tools=bound_tools,
                system_prompt=system_prompt
            )
        except TypeError:
            # Fallback: try with instructions (alternative parameter name)
            try:
                agent = create_deep_agent(
                    model=groq_llm,
                    tools=bound_tools,
                    instructions=system_prompt
                )
            except TypeError:
                # Fallback: create without system prompt, we'll add it in messages
                logger.warning("system_prompt/instructions not supported, will add to first message")
                agent = create_deep_agent(
                    model=groq_llm,
                    tools=bound_tools
                )
                # Store system prompt to add to first message
                agent._system_prompt = system_prompt
        
        logger.info(f"✅ Chat agent created successfully with {len(bound_tools)} tools using {GROQ_MODEL}")
        return agent
        
    except Exception as e:
        import traceback
        logger.error(f"Failed to create chat agent: {str(e)}\n{traceback.format_exc()}")
        raise


def invoke_agent(
    agent: Any, 
    message: str, 
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    cooperative: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Invoke the chat agent with a user message.
    
    Args:
        agent: Deep Agent instance
        message: User's message/query
        session_id: Optional session ID for conversation continuity
        thread_id: Optional thread ID for LangGraph checkpoint/memory
        cooperative: Optional cooperative ID (for logging)
        user_id: Optional user ID (for logging)
    
    Returns:
        Agent response with message and metadata
    """
    try:
        # Prepare messages for agent
        messages = []
        
        # Add system prompt if it wasn't set during agent creation
        if hasattr(agent, '_system_prompt') and agent._system_prompt:
            messages.append({"role": "system", "content": agent._system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": message})
        
        # Add session context if provided
        if session_id:
            # Deep Agents might support session context
            # For now, we'll pass it in the state
            pass
        
        # Invoke agent with thread_id for conversation memory
        # Deep Agents uses thread_id for context management via LangGraph checkpoint
        invoke_config = None
        if thread_id:
            # Use thread_id for conversation continuity
            invoke_config = {"configurable": {"thread_id": thread_id}}
            logger.debug(f"Using thread_id for conversation memory: {thread_id}")
        
        # Invoke agent with memory context
        if invoke_config:
            result = agent.invoke({"messages": messages}, config=invoke_config)
        else:
            result = agent.invoke({"messages": messages})
        
        # Extract response
        if isinstance(result, dict):
            # Get the last message from agent
            agent_messages = result.get("messages", [])
            if agent_messages:
                last_message = agent_messages[-1]
                response_text = last_message.get("content", "") if isinstance(last_message, dict) else str(last_message)
            else:
                response_text = str(result)
            
            return {
                "response": response_text,
                "session_id": session_id,
                "tools_used": result.get("tools_used", []),
                "metadata": result.get("metadata", {})
            }
        else:
            # Fallback: convert to string
            return {
                "response": str(result),
                "session_id": session_id,
                "tools_used": [],
                "metadata": {}
            }
            
    except Exception as e:
        import traceback
        logger.error(f"Agent invocation failed: {str(e)}\n{traceback.format_exc()}")
        return {
            "response": f"I encountered an error processing your request. Please try again or rephrase your question.",
            "error": str(e),
            "session_id": session_id,
            "tools_used": [],
            "metadata": {}
        }

