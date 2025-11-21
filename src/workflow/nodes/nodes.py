from src.workflow.state import ProcessingState
from src.Upload.form_extractor import extract_with_gemini, extract_pdf_metadata
from src.formatter.chunking import chunk_markdown_safe
from src.formatter.formatter import extract_form_type_from_content
from src.workflow.nodes.analysis import analyze_demo_trial
from src.database.insert import qdrant_client
from src.utils.clean_logger import CleanLogger
# LANGFUSE_CONFIGURED is now handled in langfuse_utils
import uuid
from datetime import datetime
import asyncio

# Unified Langfuse utilities - single import point
from src.utils.langfuse_utils import (
    LANGFUSE_AVAILABLE,
    safe_observe as observe,
    safe_update_observation,
    update_trace_with_error
)


@observe(name="extraction_node")
def extraction_node(state: ProcessingState) -> ProcessingState:
    """
    Node 1: Extract content from PDF/Image with validation
    
    NEW BEHAVIOR:
    - Validates file format before extraction
    - Supports both PDF and images
    - Stores validation results in state
    - Sets file_validation flag for routing
    - FIXED: Proper metadata handling for images
    
    Backward compatible: Still skips if markdown is pre-extracted
    """
    logger = CleanLogger("workflow.nodes.extraction")
    
    try:
        state["current_step"] = "extraction"
        
        # Check if markdown is already provided (from multi-report handler)
        if state.get("extracted_markdown"):
            logger.info("Using pre-extracted markdown, skipping extraction")
            
            # Still extract metadata if not already present
            if not state.get("metadata"):
                # Try to extract PDF metadata, fallback to basic metadata
                try:
                    state["metadata"] = extract_pdf_metadata(state["file_path"])
                except Exception as e:
                    logger.warning(f"Could not extract PDF metadata: {e}")
                    state["metadata"] = {
                        "source": state["file_path"],
                        "file_name": state["file_name"],
                        "extraction_method": "pre-extracted"
                    }
            
            # Mark file validation as passed (since it was pre-extracted)
            state["file_validation"] = {
                "is_valid": True,
                "file_type": "pdf",
                "format": "PDF",
                "validation_skipped": True
            }
            
            # Log to Langfuse
            safe_update_observation({
                "extraction_method": "pre-extracted",
                "file_type": state["file_validation"]["file_type"]
            })
            
            return state
        
        # NEW: Extract with validation
        logger.processing_start("file_extraction", f"File: {state['file_name']}")
        
        safe_update_observation({
            "file_name": state['file_name'],
            "file_path": state['file_path']
        })
        
        extraction_result = extract_with_gemini(
            state["file_path"], 
            validate_format=True
        )
        
        # Store validation results in state
        state["file_validation"] = extraction_result.get("validation_result", {})
        
        # Check extraction success
        if not extraction_result["success"]:
            error_msg = extraction_result.get("error", "Unknown extraction error")
            logger.processing_error("file_extraction", error_msg)
            state["errors"].append(f"File extraction failed: {error_msg}")
            
            safe_update_observation({
                "extraction_success": False,
                "error": error_msg
            })
            
            return state
        
        # Store extracted content
        state["extracted_markdown"] = extraction_result["extracted_text"]
        
        # FIXED: Handle metadata based on file type
        file_type = extraction_result.get("file_type")
        
        if file_type == "pdf":
            try:
                state["metadata"] = extract_pdf_metadata(state["file_path"])
            except Exception as e:
                logger.warning(f"Could not extract PDF metadata: {e}")
                state["metadata"] = {
                    "source": state["file_path"],
                    "file_name": state["file_name"],
                    "file_type": "pdf",
                    "error": str(e)
                }
        
        elif file_type == "image":
            validation_meta = extraction_result.get("validation_result", {}).get("metadata", {})
            state["metadata"] = {
                "source": state["file_path"],
                "file_name": state["file_name"],
                "file_type": "image",
                "format": extraction_result.get("validation_result", {}).get("format", "Unknown"),
                "width": validation_meta.get("width", 0),
                "height": validation_meta.get("height", 0),
                "file_size_mb": validation_meta.get("file_size_mb", 0),
                "mode": validation_meta.get("mode", "RGB"),
                "extraction_method": "gemini_ocr"
            }
        
        else:
            logger.warning(f"Unknown file type: {file_type}")
            state["metadata"] = {
                "source": state["file_path"],
                "file_name": state["file_name"],
                "file_type": file_type or "unknown",
                "extraction_method": "gemini_api"
            }
        
        # Log extraction success to Langfuse
        safe_update_observation({
            "extraction_success": True,
            "file_type": state['metadata'].get('file_type', 'unknown'),
            "content_length": len(state["extracted_markdown"]),
            "metadata": state["metadata"]
        })
        
        logger.processing_success("file_extraction", f"File type: {state['metadata'].get('file_type', 'unknown')}")
        
        return state
        
    except Exception as e:
        error_msg = f"Extraction failed: {str(e)}"
        logger.processing_error("file_extraction", error_msg)
        state["errors"].append(error_msg)
        
        # Log error to Langfuse
        update_trace_with_error(e, {"step": "extraction", "file_name": state.get("file_name", "unknown")})
        
        # Ensure metadata exists even on error
        if not state.get("metadata"):
            state["metadata"] = {
                "source": state.get("file_path", "unknown"),
                "file_name": state.get("file_name", "unknown"),
                "error": str(e)
            }
        
        import traceback
        traceback.print_exc()
        return state


@observe(name="analysis_node")
async def analysis_node(state: ProcessingState) -> ProcessingState:
    """Node 2: Analyze extracted content and determine form type
    
    ✅ MULTI-USER READY: Now async for non-blocking concurrent execution.
    """
    logger = CleanLogger("workflow.nodes.analysis")
    
    try:
        state["current_step"] = "analysis"
        
        if not state.get("extracted_markdown"):
            logger.processing_error("analysis", "No extracted content available for analysis")
            state["errors"].append("No extracted content available for analysis")
            return state
        
        # Log input to Langfuse
        safe_update_observation({
            "content_length": len(state["extracted_markdown"])
        })
        
        # Extract form type
        logger.processing_start("form_type_extraction", "Extracting form type from content")
        form_type = extract_form_type_from_content(state["extracted_markdown"])
        state["form_type"] = form_type
        logger.processing_success("form_type_extraction", f"Form type: {form_type}")
        
        # Perform analysis with better error handling (now async)
        # ✅ Pass user_id for multi-user tracking
        logger.analysis_start("demo_trial_analysis")
        user_id = state.get("_user_id")
        analysis_result = await analyze_demo_trial(state["extracted_markdown"], user_id=user_id)
        
        # ✅ Normalize analysis result (adds season detection, fixes structure)
        from src.formatter.json_helper import normalize_analysis_response
        analysis_result = normalize_analysis_response(analysis_result)
        
        state["analysis_result"] = analysis_result
        
        # Check analysis status
        if analysis_result.get("status") == "error":
            error_msg = analysis_result.get("error_message", "Unknown analysis error")
            logger.analysis_error("demo_trial_analysis", error_msg)
            state["errors"].append(f"Analysis error: {error_msg}")
            
            safe_update_observation({
                "analysis_success": False,
                "form_type": form_type,
                "error": error_msg
            })
        else:
            logger.analysis_result("demo_trial_analysis", analysis_result.get("metrics_detected", []), "Analysis completed successfully")
            
            safe_update_observation({
                "analysis_success": True,
                "form_type": form_type,
                "product_category": analysis_result.get("product_category", "unknown"),
                "metrics_count": len(analysis_result.get("metrics_detected", []))
            })
            
            # Log analysis summary if available
            if analysis_result.get("executive_summary"):
                logger.info(f"Executive Summary: {analysis_result.get('executive_summary')}")
        
        return state
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.analysis_error("demo_trial_analysis", error_msg)
        state["errors"].append(error_msg)
        
        update_trace_with_error(e, {"step": "analysis"})
        
        return state


@observe(name="chunking_node")
def chunking_node(state: ProcessingState) -> ProcessingState:
    """Node 3: Chunk the extracted content"""
    logger = CleanLogger("workflow.nodes.chunking")
    
    try:
        state["current_step"] = "chunking"
        
        if not state.get("extracted_markdown"):
            logger.chunking_error("No extracted content available for chunking")
            state["errors"].append("No extracted content available for chunking")
            return state
        
        # Generate chunks
        logger.chunking_start("markdown_content", len(state["extracted_markdown"]))
        chunks = chunk_markdown_safe(state["extracted_markdown"])
        if not chunks:
            logger.chunking_error("No chunks extracted from PDF")
            state["errors"].append("No chunks extracted from PDF")
            return state
            
        state["chunks"] = chunks
        
        total_chunk_size = sum(len(chunk.get("content", "")) for chunk in chunks)
        logger.chunking_result(len(chunks), total_chunk_size, "Chunking completed successfully")
        
        # Log chunking results to Langfuse
        safe_update_observation({
            "chunk_count": len(chunks),
            "total_chunk_size": total_chunk_size,
            "average_chunk_size": total_chunk_size // len(chunks) if chunks else 0
        })
        
        return state
        
    except Exception as e:
        error_msg = f"Chunking failed: {str(e)}"
        logger.chunking_error(error_msg)
        state["errors"].append(error_msg)
        
        update_trace_with_error(e, {"step": "chunking"})
        
        return state


def error_node(state: ProcessingState) -> ProcessingState:
    """Node 5: Handle errors"""
    logger = CleanLogger("workflow.nodes.error")
    
    if state["errors"]:
        logger.error(f"Processing completed with {len(state['errors'])} error(s)")
        for i, error in enumerate(state["errors"], 1):
            logger.error(f"Error {i}: {error}")
    
    return state