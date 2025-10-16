from src.workflow.state import ProcessingState
from src.Upload.form_extractor import extract_pdf_with_gemini, extract_pdf_metadata
from src.formatter.chunking import chunk_markdown_safe
from src.formatter.formatter import extract_form_type_from_content
from src.workflow.nodes.analysis import analyze_demo_trial
from src.database.insert import qdrant_client
import uuid
from datetime import datetime

def extraction_node(state: ProcessingState) -> ProcessingState:
    """Node 1: Extract content from PDF"""
    try:
        state["current_step"] = "extraction"
        
        # Extract markdown content
        extracted_content = extract_pdf_with_gemini(state["file_path"])
        if not extracted_content:
            state["errors"].append("Failed to extract content from PDF")
            return state
            
        state["extracted_markdown"] = extracted_content
        
        # Extract metadata
        state["metadata"] = extract_pdf_metadata(state["file_path"])
        
        print("✅ Extraction completed successfully")
        return state
        
    except Exception as e:
        state["errors"].append(f"Extraction failed: {str(e)}")
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