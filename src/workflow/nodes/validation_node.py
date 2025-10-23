from src.workflow.state import ProcessingState
from src.prompt.prompt_template import content_validation_template
from src.utils.llm_helper import invoke_llm  # ← Use existing helper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def content_validation_node(state: ProcessingState) -> ProcessingState:
    """
    Node: Validate if extracted content is a product demo
    
    Purpose:
    - Prevents processing of non-demo documents
    - Uses LLM to intelligently classify content
    - Sets validation flags for routing
    
    State Updates:
    - content_validation: Dict with validation results
    - is_valid_content: bool flag for routing
    
    Args:
        state: Current processing state
        
    Returns:
        Updated state with validation results
    """
    try:
        state["current_step"] = "content_validation"
        logger.info("🔍 Starting content validation...")
        
        # Check if extracted content exists
        if not state.get("extracted_markdown"):
            error_msg = "No extracted content available for validation"
            logger.error(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            state["is_valid_content"] = False
            state["content_validation"] = {
                "is_valid_demo": False,
                "confidence": 0.0,
                "content_type": "blank",
                "feedback": "No content extracted from file"
            }
            return state
        
        # Truncate content for validation (LLMs don't need full text)
        extracted_text = state["extracted_markdown"]
        text_preview = extracted_text[:3000] if len(extracted_text) > 3000 else extracted_text
        
        # Get validation prompt
        prompt_template = content_validation_template()
        validation_prompt = prompt_template.format(extracted_content=text_preview)
        
        # 🔧 FIX: Use existing invoke_llm helper
        logger.info("📤 Sending content to LLM for validation...")
        validation_result = invoke_llm(validation_prompt, as_json=True)
        
        # Parse validation result
        if validation_result and isinstance(validation_result, dict):
            state["content_validation"] = validation_result
            state["is_valid_content"] = validation_result.get("is_valid_demo", False)
            
            # Log validation result
            if validation_result["is_valid_demo"]:
                logger.info(
                    f"✅ Content validated as {validation_result.get('content_type', 'demo')} "
                    f"(confidence: {validation_result.get('confidence', 0):.2f})"
                )
            else:
                logger.warning(
                    f"❌ Content validation failed: {validation_result.get('content_type', 'unknown')} "
                    f"(confidence: {validation_result.get('confidence', 0):.2f})"
                )
                logger.warning(f"📝 Feedback: {validation_result.get('feedback', 'No feedback')}")
                
                # Add error to state for user feedback
                state["errors"].append(
                    f"Content validation failed: {validation_result.get('feedback', 'Invalid content type')}"
                )
        else:
            # Validation call failed or returned invalid format
            logger.error("❌ LLM validation returned invalid format")
            state["errors"].append("Content validation service returned invalid response")
            state["is_valid_content"] = False
            state["content_validation"] = {
                "is_valid_demo": False,
                "confidence": 0.0,
                "content_type": "unknown",
                "feedback": "Validation service error - invalid response format"
            }
        
        return state
        
    except Exception as e:
        error_msg = f"Content validation failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        
        state["errors"].append(error_msg)
        state["is_valid_content"] = False
        state["content_validation"] = {
            "is_valid_demo": False,
            "confidence": 0.0,
            "content_type": "unknown",
            "feedback": f"Validation error: {str(e)}"
        }
        return state