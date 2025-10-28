from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from src.Upload.multiple_handler import MultiReportHandler
from src.utils import constants
from src.utils.limiter_config import limiter

router = APIRouter()


@router.post("/agent")
@limiter.limit("10/minute")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload and process agricultural demo reports
    
    Supports:
    - PDF files (single or multi-report)
    - Image files (PNG, JPG, JPEG)
    
    Note: Rate limiting is handled by middleware in main.py
    """
    try:
        # Validate file type
        allowed_extensions = constants.ALLOWED_EXTENSIONS
        file_ext = '.' + file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_ext}. Supported formats: {constants.ALLOWED_EXTENSIONS}"
            )
        
        # Read file content
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        # Validate file size
        if len(content) > constants.MAX_FILE_SIZE_BYTES:
            size_mb = len(content) / (1024 * 1024)
            raise HTTPException(
                status_code=400, 
                detail=f"File too large ({size_mb:.2f}MB). Maximum size: {constants.MAX_FILE_SIZE_MB}MB"
            )
        
        # Process the file
        result = await MultiReportHandler.process_multi_report_pdf(content, file.filename)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")