"""
Chat router endpoint for chat-based agent
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from collections import OrderedDict
from src.deps.cooperative_context import get_cooperative
from src.deps.user_context import get_user_id
from src.chatbot.bot.chat_agent import create_chat_agent, invoke_agent
from src.chatbot.memory.conversation_store import generate_thread_id, get_conversation_store
from src.utils.clean_logger import get_clean_logger
from src.utils.limiter_config import limiter
from src.utils.config import (
    LANGFUSE_CONFIGURED, 
    OPENROUTER_API_KEY, 
    OPENROUTER_MODEL,
    MAX_CACHE_SIZE,
    CACHE_TTL_HOURS
)
from src.utils.openrouter_helper import is_openrouter_configured
from src.monitoring.trace.langfuse_helper import (
    observe_operation,
    update_trace_with_metrics,
    update_trace_with_error,
    get_langfuse_client
)

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = get_clean_logger(__name__)

# Cache agents per cooperative with TTL and size limits
_agent_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
# MAX_CACHE_SIZE and CACHE_TTL_HOURS are now loaded from config.py


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., description="User's message/query", min_length=1, max_length=5000)
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    reset_conversation: bool = Field(False, description="Clear conversation memory if True")
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate and sanitize message"""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        
        # Basic sanitization - remove excessive whitespace
        v = ' '.join(v.split())
        
        # Check length
        if len(v) > 5000:
            raise ValueError("Message is too long. Maximum length is 5000 characters.")
        
        return v


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
        # Input validation is handled by Pydantic
        # Additional sanitization if needed
        sanitized_message = body.message.strip()
        
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
        
        logger.info(f"Chat request from user {user_id}, cooperative {cooperative}: {sanitized_message[:100]}")
        
        # Get or create agent for this cooperative with cache management
        cache_key = f"{cooperative}"
        agent = None
        
        # Check cache with TTL
        if cache_key in _agent_cache:
            cache_entry = _agent_cache[cache_key]
            cache_time = cache_entry.get("created_at", datetime.now())
            
            # Check if cache is still valid
            if datetime.now() - cache_time < timedelta(hours=CACHE_TTL_HOURS):
                agent = cache_entry.get("agent")
                # Move to end (LRU)
                _agent_cache.move_to_end(cache_key)
                logger.debug(f"Using cached agent for cooperative: {cooperative}")
            else:
                # Cache expired, remove it
                del _agent_cache[cache_key]
                logger.debug(f"Cache expired for cooperative: {cooperative}")
        
        # Create new agent if not in cache
        if agent is None:
            logger.info(f"Creating new chat agent for cooperative: {cooperative}")
            try:
                agent = create_chat_agent(cooperative=cooperative)
                
                # Manage cache size (LRU eviction)
                if len(_agent_cache) >= MAX_CACHE_SIZE:
                    # Remove oldest entry
                    oldest_key = next(iter(_agent_cache))
                    del _agent_cache[oldest_key]
                    logger.debug(f"Cache full, evicted oldest entry: {oldest_key}")
                
                # Add to cache
                _agent_cache[cache_key] = {
                    "agent": agent,
                    "created_at": datetime.now()
                }
                logger.info(f"✅ Chat agent cached for cooperative: {cooperative}")
            except Exception as e:
                import traceback
                logger.error(f"Failed to create chat agent: {str(e)}\n{traceback.format_exc()}")
                # User-friendly error message
                raise HTTPException(
                    status_code=500,
                    detail="Unable to initialize chat service. Please try again later."
                )
        
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
            from src.chatbot.memory.simple_memory import clear_thread_memory
            clear_thread_memory(thread_id)
            logger.info(f"Conversation memory cleared for thread: {thread_id}")
        
        # Invoke agent
        try:
            result = invoke_agent(
                agent=agent,
                message=sanitized_message,
                session_id=session_id,
                thread_id=thread_id,
                cooperative=cooperative,
                user_id=user_id
            )
            
            # Extract response
            response_text = result.get("response", "I'm sorry, I couldn't process your request.")
            tools_used = result.get("tools_used", [])
            metadata = result.get("metadata", {})
            
            # Extract sources - use sources from result if available
            sources = result.get("sources", [])
            if not sources and metadata:
                # Fallback: Try to extract data sources from agent execution
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
            # User-friendly error message
            raise HTTPException(
                status_code=500,
                detail="I encountered an issue processing your request. Please try rephrasing your question or try again later."
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
        # User-friendly error message
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request. Please try again later."
        )


@router.get("/history")
@limiter.limit("60/minute")
@observe_operation(name="chat_history")
async def get_conversation_history(
    request: Request,
    session_id: str = Query(..., description="Session ID to get history for"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of messages to return"),
    cooperative: str = Depends(get_cooperative),
    user_id: str = Depends(get_user_id)
):
    """
    Get conversation history for a session.
    
    Args:
        session_id: Session ID to retrieve history for
        limit: Maximum number of messages to return (1-100)
        cooperative: Cooperative ID (from header)
        user_id: User ID (from header)
    
    Returns:
        Conversation history with messages
    """
    try:
        from src.chatbot.memory.conversation_store import get_conversation_history
        
        # Generate thread_id
        thread_id = generate_thread_id(
            cooperative=cooperative,
            user_id=user_id,
            session_id=session_id
        )
        
        # Get history
        messages = get_conversation_history(thread_id, limit=limit)
        
        return {
            "session_id": session_id,
            "thread_id": thread_id,
            "message_count": len(messages),
            "messages": messages
        }
    except Exception as e:
        import traceback
        logger.error(f"Failed to get conversation history: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve conversation history. Please try again later."
        )


@router.get("/stats")
@limiter.limit("60/minute")
@observe_operation(name="chat_stats")
async def get_conversation_stats(
    request: Request,
    session_id: Optional[str] = Query(None, description="Session ID to get stats for"),
    cooperative: str = Depends(get_cooperative),
    user_id: str = Depends(get_user_id)
):
    """
    Get conversation statistics for a session or user.
    
    Args:
        session_id: Optional session ID (if not provided, returns user-level stats)
        cooperative: Cooperative ID (from header)
        user_id: User ID (from header)
    
    Returns:
        Conversation statistics
    """
    try:
        from src.chatbot.memory.conversation_store import get_conversation_history
        
        stats = {
            "cooperative": cooperative,
            "user_id": user_id,
            "session_id": session_id,
            "total_messages": 0,
            "agent_responses": 0,
            "user_messages": 0,
            "tools_used_count": 0,
            "session_duration_minutes": None
        }
        
        if session_id:
            # Get stats for specific session
            thread_id = generate_thread_id(
                cooperative=cooperative,
                user_id=user_id,
                session_id=session_id
            )
            
            messages = get_conversation_history(thread_id, limit=1000)
            stats["total_messages"] = len(messages)
            
            # Count message types
            for msg in messages:
                role = msg.get("role", "").lower()
                if role in ["user", "human"]:
                    stats["user_messages"] += 1
                elif role in ["assistant", "ai"]:
                    stats["agent_responses"] += 1
            
            # Calculate session duration if timestamps available
            timestamps = [m.get("timestamp") for m in messages if m.get("timestamp")]
            if len(timestamps) >= 2:
                try:
                    from datetime import datetime
                    first = datetime.fromisoformat(timestamps[0]) if isinstance(timestamps[0], str) else timestamps[0]
                    last = datetime.fromisoformat(timestamps[-1]) if isinstance(timestamps[-1], str) else timestamps[-1]
                    duration = (last - first).total_seconds() / 60
                    stats["session_duration_minutes"] = round(duration, 2)
                except:
                    pass
        
        return stats
    except Exception as e:
        import traceback
        logger.error(f"Failed to get conversation stats: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve conversation statistics. Please try again later."
        )


@router.get("/health")
async def chat_health_check(
    request: Request,
    cooperative: str = Depends(get_cooperative)
):
    """
    Health check endpoint for chat agent service.
    
    Args:
        cooperative: Cooperative ID (from header)
    
    Returns:
        Health status of chat agent service
    """
    try:
        health_status = {
            "status": "healthy",
            "service": "chat_agent",
            "cooperative": cooperative,
            "cache_size": len(_agent_cache),
            "max_cache_size": MAX_CACHE_SIZE,
            "openrouter_configured": is_openrouter_configured(),
            "openrouter_model": OPENROUTER_MODEL if OPENROUTER_MODEL else None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Check if we can create an agent (quick test)
        try:
            # Just check if agent creation would work (don't actually create)
            if not is_openrouter_configured():
                health_status["status"] = "degraded"
                health_status["issues"] = ["OPENROUTER_API_KEY not configured"]
            else:
                health_status["openrouter_status"] = "configured"
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["issues"] = [str(e)]
        
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "chat_agent",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.delete("/cache")
@limiter.limit("10/minute")
async def clear_agent_cache(
    request: Request,
    cooperative: Optional[str] = Query(None, description="Cooperative ID to clear cache for (optional)"),
    cooperative_header: str = Depends(get_cooperative),
    user_id: str = Depends(get_user_id)
):
    """
    Clear agent cache (admin/maintenance endpoint).
    
    Args:
        cooperative: Optional cooperative ID (if not provided, clears all)
        cooperative_header: Cooperative ID from header (for validation)
        user_id: User ID (from header)
    
    Returns:
        Cache clearing result
    """
    try:
        cleared_count = 0
        
        if cooperative:
            # Clear specific cooperative
            if cooperative in _agent_cache:
                del _agent_cache[cooperative]
                cleared_count = 1
        else:
            # Clear all cache
            cleared_count = len(_agent_cache)
            _agent_cache.clear()
        
        logger.info(f"Agent cache cleared: {cleared_count} entries removed by user {user_id}")
        
        return {
            "cleared_count": cleared_count,
            "remaining_cache_size": len(_agent_cache)
        }
    except Exception as e:
        import traceback
        logger.error(f"Failed to clear agent cache: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Unable to clear agent cache. Please try again later."
        )

