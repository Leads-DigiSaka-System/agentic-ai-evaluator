from fastapi import APIRouter, UploadFile, File, HTTPException
from src.workflow.state import ProcessingState
from src.workflow.graph import processing_workflow
import os
import tempfile
import json

router = APIRouter()

@router.post("/agent")
async def upload_file(file: UploadFile = File(...)):
    tmp_path = None
    try:
        # Save uploaded PDF
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Initialize state for the workflow
        initial_state: ProcessingState = {
            "file_path": tmp_path,
            "file_name": file.filename,
            "file_content": content,
            "extracted_markdown": None,
            "form_type": None,
            "chunks": [],
            "analysis_result": None,
            "form_id": "",
            "metadata": {},
            "insertion_date": "",
            "current_step": "start",
            "errors": []
        }

        # Execute the workflow
        print("🚀 Starting LangGraph workflow...")
        final_state = processing_workflow.invoke(initial_state)
        
        # Check for errors
        if final_state["errors"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Processing completed with errors: {final_state['errors']}"
            )
        
        # Return structured JSON response
        response_data = {
            "status": "success",
            "file_name": file.filename,
            "form_id": final_state.get("form_id", ""),
            "form_type": final_state.get("form_type", ""),
            "extracted_content": final_state.get("extracted_markdown", ""),
            "analysis": final_state.get("analysis_result", {}),  # ENHANCED ANALYSIS HERE
            "processing_metrics": {
                "chunk_count": len(final_state.get("chunks", [])),
                "processing_steps": final_state.get("current_step", ""),
                "insertion_date": final_state.get("insertion_date", "")
            }
        }
        
        return response_data
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass