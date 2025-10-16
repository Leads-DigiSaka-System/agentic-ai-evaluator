from fastapi import APIRouter, UploadFile, File, HTTPException
from src.Upload.multiple_handler import MultiReportHandler

router = APIRouter()

@router.post("/agent")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        # Use the multi-report handler for all PDFs
        result = await MultiReportHandler.process_multi_report_pdf(content, file.filename)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")