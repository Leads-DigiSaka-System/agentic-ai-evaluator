from typing import List, Optional, Dict, Any
from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from src.core.config import OPENROUTER_MODEL, OPENROUTER_API_KEY
from src.shared.openrouter_helper import create_openrouter_llm, is_openrouter_configured
from src.shared.logging.clean_logger import get_clean_logger
from src.chatbot.prompts.system_prompt import get_chat_agent_system_prompt
from src.shared.llm_helper import get_langfuse_handler
import re
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
    
    if not is_openrouter_configured():
        raise ValueError("OPENROUTER_API_KEY is not configured. Check OPENROUTER_API_KEY in .env file")
    
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
        
        # Check if tool already has cooperative parameter
        # If it does, we can use partial binding or just pass it
        try:
            # Get the original tool's function
            original_func = tool.func if hasattr(tool, 'func') else tool
            
            # Create wrapper that injects cooperative
            def tool_wrapper(**kwargs):
                # Only add cooperative if not already present
                if 'cooperative' not in kwargs:
                    kwargs['cooperative'] = coop
                try:
                    return tool.invoke(kwargs)
                except Exception as e:
                    # Fallback: try calling with cooperative as separate arg
                    logger.debug(f"Tool invoke failed with kwargs, trying alternative: {e}")
                    try:
                        # Some tools might need cooperative passed differently
                        return tool.invoke({**kwargs, 'cooperative': coop})
                    except:
                        raise e
            
            # Create new tool with bound cooperative
            # Preserve original tool's schema if possible
            try:
                bound_tool = StructuredTool.from_function(
                    func=tool_wrapper,
                    name=tool.name,
                    description=tool.description
                )
                # Copy any additional attributes from original tool
                if hasattr(tool, 'args_schema'):
                    bound_tool.args_schema = tool.args_schema
                return bound_tool
            except Exception as e:
                logger.warning(f"Could not create StructuredTool, using original: {e}")
                return tool
        except Exception as e:
            logger.warning(f"Error binding cooperative to tool {tool.name}: {e}")
            return tool
    
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
    
    # Create OpenRouter LLM instance with Langfuse integration
    callbacks = []
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler:
        callbacks.append(langfuse_handler)
        logger.debug("Chat agent LLM initialized with Langfuse tracking")
    
    # Create OpenRouter LLM instance
    # Using free Llama 3.3 70B Instruct model via OpenRouter
    openrouter_llm = create_openrouter_llm(
        model=OPENROUTER_MODEL,
        temperature=0.7,  # Balanced creativity
        max_tokens=None,  # No limit (model has 131k context)
        callbacks=callbacks if callbacks else None
    )
    
    if not openrouter_llm:
        raise ValueError("Failed to create OpenRouter LLM. Check OPENROUTER_API_KEY configuration.")
    
    logger.info(f"🚀 OpenRouter LLM configured: {OPENROUTER_MODEL}")
    
    # Configure checkpoint saver for conversation memory
    # Deep Agents needs checkpoint saver for persistent memory
    from src.chatbot.memory.conversation_store import get_conversation_store
    checkpoint_saver = get_conversation_store()
    
    # Note: Deep Agents automatically includes file system tools and context management
    # File system tools work automatically with default StateBackend
    # Checkpoint saver enables conversation memory persistence
    
    try:
        # Deep Agents create_deep_agent signature (from docs):
        # https://docs.langchain.com/oss/python/deepagents/quickstart
        # agent = create_deep_agent(tools=[...], system_prompt=...)
        # 
        # But error logs show:
        # - system_prompt is NOT accepted (unexpected keyword argument)
        # - instructions IS required (missing required positional argument)
        # - When passing instructions, we get NotImplementedError
        #
        # This suggests the installed version might be different from docs
        # Let's try without model parameter first (docs don't show model parameter)
        
        try:
            # Method 1: Try without model (as per docs - model might be from env vars)
            agent = create_deep_agent(
                tools=bound_tools,
                instructions=system_prompt
            )
            logger.info("✅ Agent created with instructions (no model parameter)")
        except NotImplementedError as not_impl:
            # NotImplementedError - might be from inside deepagents
            # Try with model parameter (maybe required in this version)
            logger.warning(f"NotImplementedError without model: {str(not_impl)}, trying with model...")
            try:
                agent = create_deep_agent(
                    model=openrouter_llm,
                    tools=bound_tools,
                    instructions=system_prompt
                )
                logger.info("✅ Agent created with instructions and model")
            except Exception as model_error:
                logger.error(f"With model also failed: {type(model_error).__name__}: {str(model_error)}")
                # If NotImplementedError persists, it might be a library issue
                # But let's try one more thing - maybe instructions needs to be positional
                if isinstance(model_error, NotImplementedError):
                    logger.warning("NotImplementedError persists - might be a deepagents library issue")
                    logger.warning("Trying to proceed anyway or use alternative approach...")
                raise ValueError(f"Failed to create agent. Error: {str(model_error)}") from model_error
        except TypeError as type_error:
            # Check if it's about missing instructions
            error_str = str(type_error).lower()
            if "missing" in error_str and "instructions" in error_str:
                logger.warning(f"TypeError about missing instructions: {str(type_error)}")
                # Try with instructions as positional argument
                try:
                    agent = create_deep_agent(
                        openrouter_llm,
                        system_prompt,  # positional instructions
                        tools=bound_tools
                    )
                    logger.info("✅ Agent created with instructions as positional")
                except Exception as pos_error:
                    logger.error(f"Positional instructions failed: {type(pos_error).__name__}: {str(pos_error)}")
                    raise ValueError(f"Failed to create agent. Tried keyword and positional instructions. Last error: {str(pos_error)}") from pos_error
            else:
                raise
        except Exception as e:
            logger.error(f"Failed to create agent: {type(e).__name__}: {str(e)}")
            raise ValueError(f"Failed to create agent. Error: {str(e)}") from e
        
        logger.info(f"✅ Chat agent created successfully with {len(bound_tools)} tools using {OPENROUTER_MODEL}")
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
        # Deep Agents accepts both dict format and LangChain message objects
        # We'll use LangChain message objects for better compatibility
        messages = []
        
        # Add system prompt if it wasn't set during agent creation
        if hasattr(agent, '_system_prompt') and agent._system_prompt:
            # Use SystemMessage object for better compatibility
            messages.append(SystemMessage(content=agent._system_prompt))
        
        # Add user message - use HumanMessage object
        messages.append(HumanMessage(content=message))
        
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
        # Note: Timeout is handled at the tool level (30-60 seconds per tool)
        # Deep Agents will handle its own execution flow
        # For production, consider adding application-level timeout via reverse proxy or FastAPI timeout middleware
        
        try:
            if invoke_config:
                result = agent.invoke({"messages": messages}, config=invoke_config)
            else:
                result = agent.invoke({"messages": messages})
        except Exception as invoke_error:
            # Check if it's a timeout-related error
            error_str = str(invoke_error).lower()
            if "timeout" in error_str or "timed out" in error_str:
                logger.error(f"Agent invocation timed out: {invoke_error}")
                raise Exception("Request took too long to process. Please try a simpler query or try again later.")
            # Re-raise other errors to be handled by outer try-except
            raise
        
        # Extract response and tool usage from Deep Agents result
        response_text = ""
        tools_used = []
        metadata = {}
        sources = []
        
        if isinstance(result, dict):
            # Get all messages from agent execution
            agent_messages = result.get("messages", [])
            
            # Extract tools used from messages
            for msg in agent_messages:
                # Handle LangChain message types
                if isinstance(msg, ToolMessage):
                    # Tool was called - extract tool name from tool_call_id or name attribute
                    # ToolMessage.name is usually the tool_call_id, not the tool name
                    # We need to find the corresponding AIMessage with tool_calls
                    tool_call_id = getattr(msg, 'tool_call_id', None) or getattr(msg, 'name', None)
                    # Try to find the tool name from the tool_call_id
                    # For now, we'll extract from the message content or look for it in AIMessages
                    if tool_call_id:
                        # Search for the AIMessage that has this tool_call_id
                        for ai_msg in agent_messages:
                            if isinstance(ai_msg, AIMessage) and hasattr(ai_msg, 'tool_calls'):
                                for tool_call in ai_msg.tool_calls:
                                    if isinstance(tool_call, dict):
                                        call_id = tool_call.get('id') or tool_call.get('tool_call_id')
                                        if call_id == tool_call_id:
                                            tool_name = tool_call.get('name', 'unknown_tool')
                                            if tool_name not in tools_used:
                                                tools_used.append(tool_name)
                                            break
                                    elif hasattr(tool_call, 'id') and tool_call.id == tool_call_id:
                                        tool_name = getattr(tool_call, 'name', 'unknown_tool')
                                        if tool_name not in tools_used:
                                            tools_used.append(tool_name)
                                        break
                elif isinstance(msg, AIMessage):
                    # Check if message has tool_calls
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if isinstance(tool_call, dict):
                                tool_name = tool_call.get('name', 'unknown_tool')
                            else:
                                tool_name = getattr(tool_call, 'name', 'unknown_tool')
                            if tool_name and tool_name not in tools_used:
                                tools_used.append(tool_name)
                elif isinstance(msg, dict):
                    # Handle dict format messages (fallback)
                    if msg.get('type') == 'tool' or 'tool' in str(msg.get('role', '')).lower():
                        tool_name = msg.get('name', 'unknown_tool')
                        if tool_name not in tools_used:
                            tools_used.append(tool_name)
            
            # Get the last AI message as response (skip tool messages)
            # We want the final response, not intermediate tool calls
            for msg in reversed(agent_messages):
                # Skip ToolMessage and SystemMessage, we want the final AI response
                if isinstance(msg, ToolMessage) or isinstance(msg, SystemMessage):
                    continue
                    
                if isinstance(msg, AIMessage):
                    # Check if this is a final response (not just a tool call)
                    # If it has tool_calls but no content, it's waiting for tool results
                    content = getattr(msg, 'content', None)
                    has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                    
                    # Prefer messages with content (final responses)
                    if content:
                        response_text = str(content) if content else ""
                        break
                    # If no content but has tool_calls, this might be intermediate
                    # Continue searching for a message with actual content
                elif isinstance(msg, dict):
                    # Handle dict format
                    msg_type = msg.get('type', '').lower() or msg.get('role', '').lower()
                    if 'ai' in msg_type or 'assistant' in msg_type:
                        content = msg.get("content", "")
                        if content:
                            response_text = content
                            break
            
            # If no AIMessage with content found, try to get last non-tool message
            if not response_text and agent_messages:
                for msg in reversed(agent_messages):
                    if isinstance(msg, ToolMessage) or isinstance(msg, SystemMessage):
                        continue
                    if isinstance(msg, dict):
                        msg_type = msg.get('type', '').lower() or msg.get('role', '').lower()
                        if 'tool' not in msg_type:
                            response_text = msg.get("content", str(msg))
                            if response_text:
                                break
                    else:
                        # Try to extract content from any message object
                        if hasattr(msg, 'content'):
                            response_text = str(msg.content) if msg.content else ""
                            if response_text:
                                break
                        else:
                            response_text = str(msg)
                            if response_text and response_text != "None":
                                break
            
            # Extract metadata from result
            if "metadata" in result:
                metadata = result["metadata"]
            
            # Try to extract sources from tool results
            for msg in agent_messages:
                if isinstance(msg, ToolMessage):
                    # Try to parse tool result for sources
                    tool_result = getattr(msg, 'content', '')
                    if isinstance(tool_result, str):
                        # Look for product/location patterns in markdown results
                        if "product" in tool_result.lower() or "location" in tool_result.lower():
                            # Extract basic info from markdown
                            product_match = re.search(r'\*\*Product:\*\*\s*([^\n]+)', tool_result)
                            location_match = re.search(r'\*\*Location:\*\*\s*([^\n]+)', tool_result)
                            if product_match or location_match:
                                source = {}
                                if product_match:
                                    source["product"] = product_match.group(1).strip()
                                if location_match:
                                    source["location"] = location_match.group(1).strip()
                                if source and source not in sources:
                                    sources.append(source)
                                    if len(sources) >= 5:
                                        break
            
            # Fallback: if still no response text
            if not response_text:
                response_text = str(result)
        else:
            # Fallback: convert to string
            response_text = str(result)
        
        # Validate response - ensure it's not empty or just whitespace
        if not response_text or not response_text.strip():
            logger.warning("Agent returned empty response, using fallback message")
            response_text = "I received your message but couldn't generate a response. Please try rephrasing your question or try again later."
        
        # Additional validation - check if response is meaningful
        # Reject responses that are just error messages or placeholders
        response_lower = response_text.lower().strip()
        if len(response_text) < 10 or response_lower in ["none", "null", "error", ""]:
            logger.warning(f"Agent returned invalid response: {response_text[:50]}")
            response_text = "I encountered an issue generating a response. Please try rephrasing your question."
        
        return {
            "response": response_text,
            "session_id": session_id,
            "tools_used": tools_used,
            "metadata": metadata,
            "sources": sources
        }
            
    except Exception as e:
        import traceback
        logger.error(f"Agent invocation failed: {str(e)}\n{traceback.format_exc()}")
        return {
            "response": f"I encountered an error processing your request. Please try again or rephrase your question.",
            "error": str(e),
            "session_id": session_id,
            "tools_used": [],
            "metadata": {},
            "sources": []
        }

