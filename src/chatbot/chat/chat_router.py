"""
Chat router endpoint for chat-based agent
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from src.deps.cooperative_context import get_cooperative
from src.deps.user_context import get_user_id
from src.chatbot.bot.chat_agent import create_chat_agent, invoke_agent
from src.chatbot.memory.conversation_store import generate_thread_id
from src.utils.clean_logger import get_clean_logger
from src.utils.limiter_config import limiter
from src.utils.config import LANGFUSE_CONFIGURED
from src.monitoring.trace.langfuse_helper import (
    observe_operation,
    update_trace_with_metrics,
    update_trace_with_error,
    get_langfuse_client
)

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = get_clean_logger(__name__)

# Cache agents per cooperative (to avoid recreating for each request)
_agent_cache: Dict[str, Any] = {}


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., description="User's message/query")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    reset_conversation: bool = Field(False, description="Clear conversation memory if True")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    tools_used: List[str] = Field(default_factory=list, description="List of tools used by agent")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Data sources/references used")


@router.post("")
@limiter.limit("30/minute")
@observe_operation(name="chat_agent")
async def chat(
    request: Request,  # Required for rate limiter
    body: ChatRequest,
    cooperative: str = Depends(get_cooperative),
    user_id: str = Depends(get_user_id)
):
    """
    Chat endpoint for agricultural data queries.
    
    This endpoint uses Deep Agents to answer questions about:
    - Products, crops, locations, demos
    - Performance metrics and analysis
    - Reports and statistics
    
    Headers Required:
        X-Cooperative: Cooperative ID for data isolation
        X-User-ID: User ID for tracking
    
    Args:
        body: Chat request with message and optional session_id
        cooperative: Cooperative ID (from header)
        user_id: User ID (from header)
    
    Returns:
        Chat response with agent's answer and metadata
    """
    try:
        # Validate message
        if not body.message or not body.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )
        
        # Add tags to trace
        if LANGFUSE_CONFIGURED:
            try:
                client = get_langfuse_client()
                if client:
                    client.update_current_trace(
                        tags=["chat", "chat_agent", "api", f"cooperative:{cooperative}"],
                        user_id=user_id,
                        session_id=body.session_id or f"chat_{user_id}_{cooperative}"
                    )
            except Exception as e:
                logger.debug(f"Could not add tags to trace: {e}")
        
        logger.info(f"Chat request from user {user_id}, cooperative {cooperative}: {body.message[:100]}")
        
        # Get or create agent for this cooperative
        # Cache agents per cooperative to avoid recreation
        cache_key = f"{cooperative}"
        
        if cache_key not in _agent_cache:
            logger.info(f"Creating new chat agent for cooperative: {cooperative}")
            try:
                agent = create_chat_agent(cooperative=cooperative)
                _agent_cache[cache_key] = agent
                logger.info(f"✅ Chat agent cached for cooperative: {cooperative}")
            except Exception as e:
                import traceback
                logger.error(f"Failed to create chat agent: {str(e)}\n{traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize chat agent: {str(e)}"
                )
        else:
            agent = _agent_cache[cache_key]
            logger.debug(f"Using cached agent for cooperative: {cooperative}")
        
        # Generate session ID if not provided
        session_id = body.session_id
        if not session_id:
            from src.monitoring.session.langfuse_session_helper import generate_session_id
            session_id = generate_session_id(prefix=f"chat_{cooperative}_{user_id}")
        
        # Generate thread_id for conversation memory (cooperative-aware)
        thread_id = generate_thread_id(
            cooperative=cooperative,
            user_id=user_id,
            session_id=session_id
        )
        
        # Clear conversation if requested
        if body.reset_conversation:
            from src.chatbot.memory.conversation_store import clear_conversation_memory
            clear_conversation_memory(thread_id)
            logger.info(f"Conversation memory cleared for thread: {thread_id}")
        
        # Invoke agent
        try:
            result = invoke_agent(
                agent=agent,
                message=body.message,
                session_id=session_id,
                thread_id=thread_id,
                cooperative=cooperative,
                user_id=user_id
            )
            
            # Extract response
            response_text = result.get("response", "I'm sorry, I couldn't process your request.")
            tools_used = result.get("tools_used", [])
            metadata = result.get("metadata", {})
            
            # Extract sources from metadata if available
            sources = []
            if metadata:
                # Try to extract data sources from agent execution
                if "search_results" in metadata:
                    sources = metadata["search_results"][:5]  # Limit to 5 sources
                elif "results" in metadata:
                    sources = metadata["results"][:5]
            
            # Log metrics
            update_trace_with_metrics({
                "message_length": len(body.message),
                "response_length": len(response_text),
                "tools_used_count": len(tools_used),
                "session_id": session_id,
                "cooperative": cooperative,
                "user_id": user_id
            })
            
            logger.info(f"Chat response generated (tools used: {len(tools_used)})")
            
            return ChatResponse(
                response=response_text,
                session_id=session_id,
                tools_used=tools_used,
                sources=sources
            )
            
        except Exception as agent_error:
            import traceback
            logger.error(f"Agent execution failed: {str(agent_error)}\n{traceback.format_exc()}")
            update_trace_with_error(agent_error, {
                "endpoint": "chat",
                "cooperative": cooperative,
                "user_id": user_id
            })
            raise HTTPException(
                status_code=500,
                detail=f"Chat agent execution failed: {str(agent_error)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Chat endpoint error: {str(e)}\n{traceback.format_exc()}")
        update_trace_with_error(e, {
            "endpoint": "chat",
            "cooperative": cooperative,
            "user_id": user_id
        })
        raise HTTPException(
            status_code=500,
            detail=f"Chat endpoint failed: {str(e)}"
        )

