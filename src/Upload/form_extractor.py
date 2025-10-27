import pathlib
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
from src.utils.config import GOOGLE_API_KEY, GEMINI_MODEL
from langchain.document_loaders import PyMuPDFLoader
from src.prompt.prompt_template import formatting_template
from src.Upload.file_validator import FileValidator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_with_gemini(
    file_path: str, 
    validate_format: bool = True
) -> Dict[str, Any]:
    """
    Extract and process PDF/Image using Gemini API with validation
    
    NEW FUNCTION: Replaces extract_pdf_with_gemini with validation support
    
    Args:
        file_path: Path to PDF or image file
        validate_format: Whether to validate file format before extraction
        
    Returns:
        Dict with extraction results:
        {
            "success": bool,
            "extracted_text": str or None,
            "file_type": str ("pdf" or "image"),
            "validation_result": Dict (if validated),
            "error": str (if failed)
        }
    """
    result = {
        "success": False,
        "extracted_text": None,
        "file_type": None,
        "validation_result": None,
        "error": None
    }
    
    try:
        filepath = pathlib.Path(file_path)
        if not filepath.exists():
            result["error"] = f"File not found: {file_path}"
            logger.error(f"❌ {result['error']}")
            return result
        
        # Read file content
        file_content = filepath.read_bytes()
        filename = filepath.name
        
        # Step 1: Validate file format (if enabled)
        if validate_format:
            logger.info(f"🔍 Validating file format for {filename}...")
            validation_result = FileValidator.validate_file(file_content, filename)
            result["validation_result"] = validation_result
            
            if not validation_result["is_valid"]:
                result["error"] = "; ".join(validation_result["errors"])
                logger.error(f"❌ File validation failed: {result['error']}")
                return result
            
            result["file_type"] = validation_result["file_type"]
            logger.info(FileValidator.get_validation_summary(validation_result))
        else:
            # Infer file type from extension
            file_ext = filepath.suffix.lower()
            if file_ext == '.pdf':
                result["file_type"] = "pdf"
            elif file_ext in {'.png', '.jpg', '.jpeg'}:
                result["file_type"] = "image"
            else:
                result["error"] = f"Unsupported file type: {file_ext}"
                return result
        
        # Step 2: Extract content with Gemini
        logger.info(f"🚀 Starting Gemini extraction for {filename}...")
        extracted_text = _extract_with_gemini_api(file_content, filepath, result["file_type"])
        
        if extracted_text:
            result["success"] = True
            result["extracted_text"] = extracted_text
            logger.info(f"✅ Extraction completed successfully ({len(extracted_text)} characters)")
        else:
            result["error"] = "No content extracted from file"
            logger.error("❌ Extraction returned no content")
        
        return result
        
    except Exception as e:
        result["error"] = f"Extraction failed: {str(e)}"
        logger.error(f"❌ {result['error']}")
        import traceback
        traceback.print_exc()
        return result


def _extract_with_gemini_api(
    file_content: bytes, 
    filepath: pathlib.Path, 
    file_type: str
) -> Optional[str]:
    """
    Internal function: Call Gemini API for extraction
    
    Handles both PDF and Image files using appropriate MIME types
    
    Args:
        file_content: Raw file bytes
        filepath: Path object for file
        file_type: "pdf" or "image"
        
    Returns:
        Extracted text or None
    """
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        file_size = len(file_content)
        
        logger.info(f"📊 File size: {file_size / (1024*1024):.2f} MB")
        
        # Get extraction prompt template
        prompt_template = formatting_template()
        extraction_prompt = prompt_template.template
        
        # Determine MIME type based on file type
        if file_type == "pdf":
            mime_type = 'application/pdf'
        elif file_type == "image":
            # Detect image format from extension
            ext = filepath.suffix.lower()
            if ext == '.png':
                mime_type = 'image/png'
            elif ext in {'.jpg', '.jpeg'}:
                mime_type = 'image/jpeg'
            else:
                mime_type = 'image/jpeg'  # Default
        else:
            logger.error(f"❌ Unsupported file type: {file_type}")
            return None
        
        # Choose processing method based on file size
        if file_size < 20 * 1024 * 1024:  # 20MB threshold
            logger.info("📤 Processing with inline method...")
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(
                        data=file_content,
                        mime_type=mime_type,
                    ),
                    extraction_prompt
                ]
            )
        else:
            logger.info("📤 Processing with File API method (large file)...")
            sample_file = client.files.upload(file=filepath)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[sample_file, extraction_prompt]
            )
        
        # Extract text from response
        if response.candidates and response.candidates[0].content.parts:
            extracted_text = "".join(part.text for part in response.candidates[0].content.parts)
            logger.info(f"✅ Gemini API extraction successful")
            return extracted_text
        else:
            logger.error("❌ No content in Gemini response")
            return None
            
    except Exception as e:
        logger.error(f"❌ Gemini API extraction failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# ============================================
# BACKWARD COMPATIBILITY WRAPPER
# ============================================
def extract_pdf_with_gemini(pdf_path: str) -> Optional[str]:
    """
    LEGACY FUNCTION: Maintained for backward compatibility
    
    Wraps new extract_with_gemini function
    Used by existing code that expects simple string return
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text or None
    """
    logger.warning("⚠️  Using legacy extract_pdf_with_gemini - consider migrating to extract_with_gemini")
    result = extract_with_gemini(pdf_path, validate_format=True)
    return result["extracted_text"]


def extract_pdf_metadata(pdf_path: str) -> Dict[str, Any]:
    """
    Extract metadata from PDF using PyMuPDFLoader
    
    UPDATED: Now handles non-PDF files gracefully (e.g., images)
    Returns basic metadata if not a PDF
    """
    try:
        # Check if file is actually a PDF
        import pathlib
        filepath = pathlib.Path(pdf_path)
        
        if not filepath.exists():
            return {
                "error": "File not found",
                "source": pdf_path,
                "file_type": "unknown"
            }
        
        file_ext = filepath.suffix.lower()
        
        # If it's an image, return basic metadata (don't try PDF extraction)
        if file_ext in {'.png', '.jpg', '.jpeg'}:
            from PIL import Image
            try:
                img = Image.open(filepath)
                return {
                    "source": pdf_path,
                    "file_name": filepath.name,
                    "file_type": "image",
                    "format": img.format,
                    "mode": img.mode,
                    "width": img.size[0],
                    "height": img.size[1],
                    "extraction_method": "PIL"
                }
            except Exception as e:
                return {
                    "source": pdf_path,
                    "file_name": filepath.name,
                    "file_type": "image",
                    "error": f"Could not read image metadata: {str(e)}"
                }
        
        # Try PDF metadata extraction
        loader = PyMuPDFLoader(pdf_path)
        document = loader.load([0])[0]  # First page only for metadata
        return document.metadata
        
    except Exception as e:
        # Return minimal metadata on error
        return {
            "error": str(e),
            "source": pdf_path,
            "file_type": "unknown"
        }