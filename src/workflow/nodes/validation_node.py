from src.workflow.state import ProcessingState
from src.prompt.prompt_template import content_validation_template
from src.utils.llm_helper import invoke_llm  # ← Use existing helper
from src.utils.clean_logger import CleanLogger


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
    logger = CleanLogger("workflow.nodes.validation")
    
    try:
        state["current_step"] = "content_validation"
        logger.validation_start("content_validation")
        
        # Check if extracted content exists
        if not state.get("extracted_markdown"):
            error_msg = "No extracted content available for validation"
            logger.validation_error("content_validation", error_msg)
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
        logger.llm_request("gemini", "content_validation")
        validation_result = invoke_llm(validation_prompt, as_json=True)
        
        # Parse validation result
        if validation_result and isinstance(validation_result, dict):
            state["content_validation"] = validation_result
            state["is_valid_content"] = validation_result.get("is_valid_demo", False)
            
            # Log validation result
            if validation_result["is_valid_demo"]:
                confidence = validation_result.get('confidence', 0)
                content_type = validation_result.get('content_type', 'demo')
                logger.validation_result("content_validation", f"Valid {content_type}", confidence)
            else:
                confidence = validation_result.get('confidence', 0)
                content_type = validation_result.get('content_type', 'unknown')
                logger.validation_result("content_validation", f"Invalid {content_type}", confidence)
                logger.info(f"Validation feedback: {validation_result.get('feedback', 'No feedback')}")
                
                # Add error to state for user feedback
                state["errors"].append(
                    f"Content validation failed: {validation_result.get('feedback', 'Invalid content type')}"
                )
        else:
            # Validation call failed or returned invalid format
            logger.validation_error("content_validation", "LLM validation returned invalid format")
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
        logger.validation_error("content_validation", error_msg)
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