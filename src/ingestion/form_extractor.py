import pathlib
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
from src.core.config import GOOGLE_API_KEY, GEMINI_LARGE
from langchain_community.document_loaders import PyMuPDFLoader
from src.prompts.prompt_template import formatting_template, handwritten_form_template
from src.ingestion.file_validator import FileValidator
from src.shared.logging.clean_logger import get_clean_logger


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
    logger = get_clean_logger(__name__)
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
            logger.file_error(filepath.name, result['error'])
            return result
        
        # Read file content
        file_content = filepath.read_bytes()
        filename = filepath.name
        
        # Step 1: Validate file format (if enabled)
        if validate_format:
            logger.file_validation(filename, "validating format")
            validation_result = FileValidator.validate_file(file_content, filename)
            result["validation_result"] = validation_result
            
            if not validation_result["is_valid"]:
                result["error"] = "; ".join(validation_result["errors"])
                logger.file_validation(filename, "failed", result['error'])
                return result
            
            result["file_type"] = validation_result["file_type"]
            logger.file_validation(filename, "passed", FileValidator.get_validation_summary(validation_result))
        else:
            # Infer file type from extension
            file_ext = filepath.suffix.lower()
            if file_ext == '.pdf':
                result["file_type"] = "pdf"
            elif file_ext in {'.png', '.jpg', '.jpeg'}:
                result["file_type"] = "image"
            else:
                result["error"] = f"Unsupported file type: {file_ext}"
                logger.file_error(filename, result['error'])
                return result
        
        # Step 2: Detect content type (handwritten form, typed, or mixed)
        # Works for both images AND PDFs (PDFs can contain images of handwritten forms)
        content_type = _detect_content_type(file_content, filepath, result["file_type"], logger)
        logger.info(f"Detected content type: {content_type} (file type: {result['file_type']})")
        
        # Step 3: Extract content with Gemini (with automatic prompt selection)
        logger.file_extraction(filename, result["file_type"], len(file_content))
        extracted_text = _extract_with_gemini_api(
            file_content, 
            filepath, 
            result["file_type"],
            content_type
        )
        
        if extracted_text:
            result["success"] = True
            result["extracted_text"] = extracted_text
            logger.file_extraction(filename, result["file_type"], len(extracted_text))
            logger.info("Extraction completed successfully")
        else:
            result["error"] = "No content extracted from file"
            logger.file_error(filename, "Extraction returned no content")
        
        return result
        
    except Exception as e:
        result["error"] = f"Extraction failed: {str(e)}"
        logger.file_error(filepath.name if 'filepath' in locals() else "unknown", result['error'])
        import traceback
        traceback.print_exc()
        return result


def _detect_content_type(
    file_content: bytes, 
    filepath: pathlib.Path, 
    file_type: str,
    logger
) -> str:
    """
    Detect if file contains handwritten forms
    
    Uses a lightweight Gemini call to classify content type
    Returns: "handwritten_form", "typed", or "mixed"
    """
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        # Detection prompt
        if file_type == "pdf":
            detection_prompt = """Analyze this PDF quickly. Does it contain:
1. FORMS with HANDWRITTEN entries = "handwritten_form"
2. TYPED/PRINTED text = "typed"
3. MIXED (printed form with handwritten fields) = "mixed"

Respond with ONLY: "handwritten_form", "typed", or "mixed"
"""
        else:
            detection_prompt = """Analyze this image quickly. Is it:
1. A FORM with HANDWRITTEN entries = "handwritten_form"
2. TYPED/PRINTED document = "typed"
3. MIXED (printed form with handwritten fields) = "mixed"

Respond with ONLY: "handwritten_form", "typed", or "mixed"
"""
        
        # Determine MIME type
        if file_type == "pdf":
            mime_type = 'application/pdf'
        else:
            ext = filepath.suffix.lower()
            mime_type = 'image/png' if ext == '.png' else 'image/jpeg'
        
        # Use simple call without config for detection (lightweight)
        response = client.models.generate_content(
            model=GEMINI_LARGE,
            contents=[
                types.Part.from_bytes(data=file_content, mime_type=mime_type),
                detection_prompt
            ]
        )
        
        if response.candidates and response.candidates[0].content.parts:
            result = response.candidates[0].content.parts[0].text.strip().lower()
            if "handwritten" in result or "form" in result:
                return "handwritten_form"
            elif "mixed" in result:
                return "mixed"
            else:
                return "typed"
        
        # Default to handwritten_form for safety
        return "handwritten_form"
        
    except Exception as e:
        logger.warning(f"Content detection failed: {e}, defaulting to handwritten_form")
        return "handwritten_form"


def _extract_with_gemini_api(
    file_content: bytes, 
    filepath: pathlib.Path, 
    file_type: str,
    content_type: str
) -> Optional[str]:
    """
    Internal function: Call Gemini API for extraction with automatic prompt selection
    
    Handles both PDF and Image files using appropriate MIME types
    Automatically selects prompt based on content type (handwritten vs typed)
    
    Args:
        file_content: Raw file bytes
        filepath: Path object for file
        file_type: "pdf" or "image"
        content_type: "handwritten_form", "typed", or "mixed"
        
    Returns:
        Extracted text or None
    """
    logger = get_clean_logger(__name__)
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        file_size = len(file_content)
        
        logger.info(f"File size: {file_size / (1024*1024):.2f} MB")
        
        # Select appropriate prompt based on content type
        if content_type == "handwritten_form" or content_type == "mixed":
            prompt_template = handwritten_form_template()
            extraction_prompt = prompt_template.template
            logger.info(f"Using handwritten form prompt for {content_type}")
        else:
            prompt_template = formatting_template()
            extraction_prompt = prompt_template.template
            logger.info("Using structured extraction prompt")
        
        # Determine MIME type based on file type
        if file_type == "pdf":
            mime_type = 'application/pdf'
        elif file_type == "image":
            ext = filepath.suffix.lower()
            if ext == '.png':
                mime_type = 'image/png'
            elif ext in {'.jpg', '.jpeg'}:
                mime_type = 'image/jpeg'
            else:
                mime_type = 'image/jpeg'  # Default
        else:
            logger.error(f"Unsupported file type: {file_type}")
            return None
        
        # VLM processes images directly - no separate OCR needed
        # Note: Using default config (no GenerationConfig) due to SDK compatibility
        # The specialized prompt is more important than config settings for VLM
        
        # Choose processing method based on file size
        if file_size < 20 * 1024 * 1024:  # 20MB threshold
            logger.info("Processing with inline method")
            response = client.models.generate_content(
                model=GEMINI_LARGE,
                contents=[
                    types.Part.from_bytes(data=file_content, mime_type=mime_type),
                    extraction_prompt
                ]
            )
        else:
            logger.info("Processing with File API method (large file)")
            sample_file = client.files.upload(file=filepath)
            response = client.models.generate_content(
                model=GEMINI_LARGE,
                contents=[sample_file, extraction_prompt]
            )
        
        # Extract text from response
        if response.candidates and response.candidates[0].content.parts:
            extracted_text = "".join(part.text for part in response.candidates[0].content.parts)
            logger.info("Gemini API extraction successful")
            return extracted_text
        else:
            logger.error("No content in Gemini response")
            return None
            
    except Exception as e:
        logger.error(f"Gemini API extraction failed: {str(e)}")
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
    logger = get_clean_logger(__name__)
    logger.warning("Using legacy extract_pdf_with_gemini - consider migrating to extract_with_gemini")
    result = extract_with_gemini(pdf_path, validate_format=True)
    return result["extracted_text"]


def extract_pdf_metadata(pdf_path: str) -> Dict[str, Any]:
    """
    Extract metadata from PDF using PyMuPDFLoader
    
    UPDATED: Now handles non-PDF files gracefully (e.g., images)
    Returns basic metadata if not a PDF
    """
    logger = get_clean_logger(__name__)
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