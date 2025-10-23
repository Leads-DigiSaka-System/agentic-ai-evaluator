from src.workflow.state import ProcessingState
from src.Upload.form_extractor import extract_with_gemini, extract_pdf_metadata
from src.formatter.chunking import chunk_markdown_safe
from src.formatter.formatter import extract_form_type_from_content
from src.workflow.nodes.analysis import analyze_demo_trial
from src.database.insert import qdrant_client
import uuid
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    try:
        state["current_step"] = "extraction"
        
        # Check if markdown is already provided (from multi-report handler)
        if state.get("extracted_markdown"):
            logger.info("✅ Using pre-extracted markdown, skipping extraction")
            
            # Still extract metadata if not already present
            if not state.get("metadata"):
                # Try to extract PDF metadata, fallback to basic metadata
                try:
                    state["metadata"] = extract_pdf_metadata(state["file_path"])
                except Exception as e:
                    logger.warning(f"⚠️ Could not extract PDF metadata: {e}")
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
        logger.info(f"🔍 Extracting and validating file: {state['file_name']}")
        extraction_result = extract_with_gemini(
            state["file_path"], 
            validate_format=True  # Enable format validation
        )
        
        # Store validation results in state
        state["file_validation"] = extraction_result.get("validation_result", {})
        
        # Check extraction success
        if not extraction_result["success"]:
            error_msg = extraction_result.get("error", "Unknown extraction error")
            logger.error(f"❌ Extraction failed: {error_msg}")
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
                logger.warning(f"⚠️ Could not extract PDF metadata: {e}")
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
            logger.warning(f"⚠️ Unknown file type: {file_type}")
            state["metadata"] = {
                "source": state["file_path"],
                "file_name": state["file_name"],
                "file_type": file_type or "unknown",
                "extraction_method": "gemini_api"
            }
        
        logger.info("✅ Extraction completed successfully")
        logger.info(f"📊 Metadata: {state['metadata'].get('file_type', 'unknown')} - {state['metadata'].get('format', 'N/A')}")
        
        return state
        
    except Exception as e:
        error_msg = f"Extraction failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
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
    try:
        state["current_step"] = "analysis"
        
        if not state.get("extracted_markdown"):
            state["errors"].append("No extracted content available for analysis")
            return state
        
        # Extract form type
        form_type = extract_form_type_from_content(state["extracted_markdown"])
        state["form_type"] = form_type
        print(f"📋 Extracted form type: {form_type}")
        
        # Perform analysis with better error handling
        analysis_result = analyze_demo_trial(state["extracted_markdown"])
        state["analysis_result"] = analysis_result
        
        # Check analysis status
        if analysis_result.get("status") == "error":
            error_msg = analysis_result.get("error_message", "Unknown analysis error")
            print(f"⚠️ Analysis completed with errors: {error_msg}")
            state["errors"].append(f"Analysis error: {error_msg}")
        else:
            print("✅ Analysis completed successfully")
            # Log analysis summary if available
            if analysis_result.get("executive_summary"):
                print(f"📈 Executive Summary: {analysis_result.get('executive_summary')}")
        
        return state
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        print(f"❌ {error_msg}")
        state["errors"].append(error_msg)
        return state

def chunking_node(state: ProcessingState) -> ProcessingState:
    """Node 3: Chunk the extracted content"""
    try:
        state["current_step"] = "chunking"
        
        if not state.get("extracted_markdown"):
            state["errors"].append("No extracted content available for chunking")
            return state
        
        # Generate chunks
        chunks = chunk_markdown_safe(state["extracted_markdown"])
        if not chunks:
            state["errors"].append("No chunks extracted from PDF")
            return state
            
        state["chunks"] = chunks
        print(f"📊 Total chunks created: {len(chunks)}")
        
        return state
        
    except Exception as e:
        state["errors"].append(f"Chunking failed: {str(e)}")
        return state

def storage_node(state: ProcessingState) -> ProcessingState:
    """Node 4: Prepare and store data in vector database"""
    try:
        state["current_step"] = "storage"
        
        if not state.get("chunks"):
            state["errors"].append("No chunks available for storage")
            return state
        
        # Generate unique IDs and timestamps
        state["form_id"] = str(uuid.uuid4())
        state["insertion_date"] = datetime.now().isoformat()
        
        # Enhanced metadata with analysis results - FIXED nested access
        analysis_data = state.get("analysis_result", {})
        basic_info = analysis_data.get("basic_info", {})
        efficacy_analysis = analysis_data.get("efficacy_analysis", {})
        averages = efficacy_analysis.get("averages", {})
        
        metadata = {
            "form_id": state["form_id"],
            "form_title": state["file_name"],
            "form_type": state.get("form_type", "unknown"),
            "date_of_insertion": state["insertion_date"],
            "analysis_status": analysis_data.get("status", "unknown"),
            "cooperator": basic_info.get("cooperator", ""),
            "product": basic_info.get("product", ""),
            "location": basic_info.get("location", ""),
            "improvement_percent": averages.get("improvement_percent", 0)
        }
        
        # Attach metadata to chunks
        for chunk in state["chunks"]:
            chunk["metadata"] = metadata.copy()
        
        # Insert into Qdrant
        insert_success = qdrant_client.insert_chunks(state["chunks"])
        if insert_success:
            print("✅ Successfully stored in vector database")
            print(f"🆔 Form ID: {state['form_id']}")
        else:
            state["errors"].append("Failed to store chunks in database")
        
        return state
        
    except Exception as e:
        state["errors"].append(f"Storage failed: {str(e)}")
        return state

def error_node(state: ProcessingState) -> ProcessingState:
    """Node 5: Handle errors"""
    if state["errors"]:
        print(f"❌ Processing completed with {len(state['errors'])} error(s):")
        for i, error in enumerate(state["errors"], 1):
            print(f"   {i}. {error}")
    return state