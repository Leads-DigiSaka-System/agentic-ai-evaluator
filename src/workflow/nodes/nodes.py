from src.workflow.state import ProcessingState
from src.Upload.form_extractor import extract_with_gemini, extract_pdf_metadata
from src.formatter.chunking import chunk_markdown_safe
from src.formatter.formatter import extract_form_type_from_content
from src.workflow.nodes.analysis import analyze_demo_trial
from src.database.insert import qdrant_client
from src.utils.clean_logger import CleanLogger
import uuid
from datetime import datetime

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
                "file_type": "pdf",  # Assume PDF for pre-extracted content
                "format": "PDF",
                "validation_skipped": True
            }
            
            return state
        
        # NEW: Extract with validation
        logger.processing_start("file_extraction", f"File: {state['file_name']}")
        
        # Get trace_id for Langfuse tracking
        trace_id = state.get("_langfuse_trace_id")
        
        # Create span for extraction node
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name="extraction_node",
                    trace_id=trace_id,
                    input_data={"file_name": state["file_name"], "file_path": state["file_path"]},
                    metadata={"node": "extraction", "step": "file_extraction"}
                )
            except Exception as e:
                logger.warning(f"Failed to create extraction span: {e}")
        
        extraction_result = extract_with_gemini(
            state["file_path"], 
            validate_format=True,  # Enable format validation
            trace_id=trace_id
        )
        
        # Store validation results in state
        state["file_validation"] = extraction_result.get("validation_result", {})
        
        # Check extraction success
        if not extraction_result["success"]:
            error_msg = extraction_result.get("error", "Unknown extraction error")
            logger.processing_error("file_extraction", error_msg)
            state["errors"].append(f"File extraction failed: {error_msg}")
            return state
        
        # Store extracted content
        state["extracted_markdown"] = extraction_result["extracted_text"]
        
        # FIXED: Handle metadata based on file type
        file_type = extraction_result.get("file_type")
        
        if file_type == "pdf":
            # Extract rich metadata from PDF
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
            # FIXED: Create proper metadata for images
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
            # Fallback for unknown file types (should not happen with validation)
            logger.warning(f"Unknown file type: {file_type}")
            state["metadata"] = {
                "source": state["file_path"],
                "file_name": state["file_name"],
                "file_type": file_type or "unknown",
                "extraction_method": "gemini_api"
            }
        
        logger.processing_success("file_extraction", f"File type: {state['metadata'].get('file_type', 'unknown')}")
        
        # Update span with output data
        if trace_id and extraction_result["success"]:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name="extraction_node",
                    trace_id=trace_id,
                    output_data={
                        "file_type": extraction_result.get("file_type"),
                        "extraction_success": True,
                        "content_length": len(extraction_result.get("extracted_text", ""))
                    },
                    metadata={"node": "extraction", "step": "file_extraction", "status": "success"}
                )
            except Exception:
                pass  # Span already created, just updating if possible
        
        return state
        
    except Exception as e:
        error_msg = f"Extraction failed: {str(e)}"
        logger.processing_error("file_extraction", error_msg)
        state["errors"].append(error_msg)
        
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
def analysis_node(state: ProcessingState) -> ProcessingState:
    """Node 2: Analyze extracted content and determine form type"""
    logger = CleanLogger("workflow.nodes.analysis")
    
    try:
        state["current_step"] = "analysis"
        
        if not state.get("extracted_markdown"):
            logger.processing_error("analysis", "No extracted content available for analysis")
            state["errors"].append("No extracted content available for analysis")
            return state
        
        # Get trace_id for Langfuse tracking
        trace_id = state.get("_langfuse_trace_id")
        
        # Create span for analysis node
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name="analysis_node",
                    trace_id=trace_id,
                    input_data={"file_name": state.get("file_name"), "content_length": len(state["extracted_markdown"])},
                    metadata={"node": "analysis", "step": "analysis"}
                )
            except Exception as e:
                logger.warning(f"Failed to create analysis span: {e}")
        
        # Extract form type
        logger.processing_start("form_type_extraction", "Extracting form type from content")
        form_type = extract_form_type_from_content(state["extracted_markdown"])
        state["form_type"] = form_type
        logger.processing_success("form_type_extraction", f"Form type: {form_type}")
        
        # Perform analysis with better error handling
        logger.analysis_start("demo_trial_analysis")
        analysis_result = analyze_demo_trial(state["extracted_markdown"], trace_id=trace_id)
        state["analysis_result"] = analysis_result
        
        # Check analysis status
        if analysis_result.get("status") == "error":
            error_msg = analysis_result.get("error_message", "Unknown analysis error")
            logger.analysis_error("demo_trial_analysis", error_msg)
            state["errors"].append(f"Analysis error: {error_msg}")
        else:
            logger.analysis_result("demo_trial_analysis", analysis_result.get("metrics_detected", []), "Analysis completed successfully")
            # Log analysis summary if available
            if analysis_result.get("executive_summary"):
                logger.info(f"Executive Summary: {analysis_result.get('executive_summary')}")
            
            # Update span with output data
            if trace_id:
                try:
                    from src.utils.langfuse_helper import create_span
                    create_span(
                        name="analysis_node",
                        trace_id=trace_id,
                        output_data={
                            "form_type": form_type,
                            "analysis_status": "success",
                            "metrics_count": len(analysis_result.get("metrics_detected", []))
                        },
                        metadata={"node": "analysis", "step": "analysis", "status": "success"}
                    )
                except Exception:
                    pass  # Span already created
        
        return state
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.analysis_error("demo_trial_analysis", error_msg)
        state["errors"].append(error_msg)
        return state

def chunking_node(state: ProcessingState) -> ProcessingState:
    """Node 3: Chunk the extracted content"""
    logger = CleanLogger("workflow.nodes.chunking")
    
    try:
        state["current_step"] = "chunking"
        
        if not state.get("extracted_markdown"):
            logger.chunking_error("No extracted content available for chunking")
            state["errors"].append("No extracted content available for chunking")
            return state
        
        # Get trace_id for Langfuse tracking
        trace_id = state.get("_langfuse_trace_id")
        
        # Create span for chunking node
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name="chunking_node",
                    trace_id=trace_id,
                    input_data={"content_length": len(state["extracted_markdown"])},
                    metadata={"node": "chunking", "step": "chunking"}
                )
            except Exception as e:
                logger.warning(f"Failed to create chunking span: {e}")
        
        # Generate chunks
        logger.chunking_start("markdown_content", len(state["extracted_markdown"]))
        chunks = chunk_markdown_safe(state["extracted_markdown"])
        if not chunks:
            logger.chunking_error("No chunks extracted from PDF")
            state["errors"].append("No chunks extracted from PDF")
            return state
            
        state["chunks"] = chunks
        chunk_count = len(chunks)
        total_chunk_size = sum(len(chunk.get("content", "")) for chunk in chunks)
        logger.chunking_result(chunk_count, total_chunk_size, "Chunking completed successfully")
        
        # Update span with output data
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name="chunking_node",
                    trace_id=trace_id,
                    output_data={
                        "chunk_count": chunk_count,
                        "total_chunk_size": total_chunk_size,
                        "chunking_success": True
                    },
                    metadata={"node": "chunking", "step": "chunking", "status": "success"}
                )
            except Exception:
                pass  # Span already created
        
        return state
        
    except Exception as e:
        error_msg = f"Chunking failed: {str(e)}"
        logger.chunking_error(error_msg)
        state["errors"].append(error_msg)
        return state

def error_node(state: ProcessingState) -> ProcessingState:
    """Node 5: Handle errors"""
    logger = CleanLogger("workflow.nodes.error")
    
    # Get trace_id for Langfuse tracking
    trace_id = state.get("_langfuse_trace_id")
    
    if state["errors"]:
        error_count = len(state["errors"])
        logger.error(f"Processing completed with {error_count} error(s)")
        
        # Create span for error node
        if trace_id:
            try:
                from src.utils.langfuse_helper import create_span
                create_span(
                    name="error_node",
                    trace_id=trace_id,
                    input_data={"error_count": error_count},
                    output_data={"errors": state["errors"][:10]},  # Limit to first 10 errors
                    metadata={"node": "error", "step": "error_handling", "level": "ERROR"},
                    level="ERROR"
                )
            except Exception as e:
                logger.warning(f"Failed to create error span: {e}")
        
        for i, error in enumerate(state["errors"], 1):
            logger.error(f"Error {i}: {error}")
    return state