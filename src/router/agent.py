from fastapi import APIRouter, UploadFile, File, HTTPException
from src.Upload.multiple_handler import MultiReportHandler

router = APIRouter()

@router.post("/agent")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload and process agricultural demo reports
    
    Supports:
    - PDF files (single or multi-report)
    - Image files (PNG, JPG, JPEG)
    """
    try:
        # Validate file type - UPDATED to support images
        allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg'}
        file_ext = '.' + file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_ext}. Supported formats: PDF, PNG, JPG, JPEG"
            )
        
        # Read file content
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        # Validate file size (50MB limit from FileValidator)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(content) > max_size:
            size_mb = len(content) / (1024 * 1024)
            raise HTTPException(
                status_code=400, 
                detail=f"File too large ({size_mb:.2f}MB). Maximum size: 50MB"
            )
        
        # Use the multi-report handler for all files
        # Note: Images are always single report
        result = await MultiReportHandler.process_multi_report_pdf(content, file.filename)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")