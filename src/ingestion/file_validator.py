# file: src/Upload/file_validator.py

import io
import pathlib
from typing import Dict, Tuple, Optional
from PIL import Image
import PyPDF2
from src.shared.logging.clean_logger import get_clean_logger


class FileValidator:
    """
    Validates file formats and integrity before processing
    
    Supports:
    - PDF files (with structure validation)
    - Image files (PNG, JPG, JPEG)
    """
    
    # Supported file types
    SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
    SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
    
    # File size limits (in bytes)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MIN_FILE_SIZE = 1024  # 1KB
    
    @staticmethod
    def validate_file(file_content: bytes, filename: str) -> Dict[str, any]:
        """
        Main validation function - validates file format and integrity
        
        Args:
            file_content: Raw file bytes
            filename: Original filename with extension
            
        Returns:
            Dict with validation results:
            {
                "is_valid": bool,
                "file_type": str ("pdf" | "image"),
                "format": str (e.g., "PDF", "PNG"),
                "errors": List[str],
                "warnings": List[str],
                "metadata": Dict (file-specific info)
            }
        """
        logger = get_clean_logger(__name__)
        result = {
            "is_valid": False,
            "file_type": None,
            "format": None,
            "errors": [],
            "warnings": [],
            "metadata": {}
        }
        
        # Step 1: Validate file size
        size_valid, size_error = FileValidator._validate_file_size(file_content)
        if not size_valid:
            result["errors"].append(size_error)
            return result
        
        # Step 2: Detect file type from extension
        file_ext = pathlib.Path(filename).suffix.lower()
        
        if file_ext in FileValidator.SUPPORTED_PDF_EXTENSIONS:
            # Validate PDF
            return FileValidator._validate_pdf(file_content, filename)
            
        elif file_ext in FileValidator.SUPPORTED_IMAGE_EXTENSIONS:
            # Validate Image
            return FileValidator._validate_image(file_content, filename, file_ext)
            
        else:
            # Unsupported format
            result["errors"].append(
                f"Unsupported file format: {file_ext}. "
                f"Supported formats: PDF, PNG, JPG, JPEG"
            )
            return result
    
    @staticmethod
    def _validate_file_size(file_content: bytes) -> Tuple[bool, Optional[str]]:
        """Validate file size is within acceptable range"""
        size = len(file_content)
        
        if size < FileValidator.MIN_FILE_SIZE:
            return False, f"File too small ({size} bytes). Minimum: {FileValidator.MIN_FILE_SIZE} bytes"
        
        if size > FileValidator.MAX_FILE_SIZE:
            size_mb = size / (1024 * 1024)
            max_mb = FileValidator.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File too large ({size_mb:.2f}MB). Maximum: {max_mb}MB"
        
        return True, None
    
    @staticmethod
    def _validate_pdf(file_content: bytes, filename: str) -> Dict[str, any]:
        """
        Validate PDF file structure and integrity
        
        Checks:
        1. File is a valid PDF
        2. PDF is not encrypted
        3. PDF has readable pages
        4. PDF metadata is accessible
        """
        result = {
            "is_valid": False,
            "file_type": "pdf",
            "format": "PDF",
            "errors": [],
            "warnings": [],
            "metadata": {}
        }
        
        try:
            # Create PDF reader from bytes
            pdf_stream = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            
            # Check 1: Verify PDF is not encrypted
            if pdf_reader.is_encrypted:
                result["errors"].append("PDF is encrypted. Please provide an unencrypted PDF.")
                return result
            
            # Check 2: Verify PDF has pages
            num_pages = len(pdf_reader.pages)
            if num_pages == 0:
                result["errors"].append("PDF contains no pages")
                return result
            
            # Check 3: Try to read first page (verifies PDF structure)
            try:
                first_page = pdf_reader.pages[0]
                text_sample = first_page.extract_text()
                
                # Warn if first page has no text (might be image-only PDF)
                if not text_sample or len(text_sample.strip()) < 10:
                    result["warnings"].append(
                        "PDF first page contains little or no text. "
                        "This may be a scanned document (will still be processed)."
                    )
            except Exception as e:
                result["errors"].append(f"Cannot read PDF pages: {str(e)}")
                return result
            
            # Extract metadata
            metadata = pdf_reader.metadata
            result["metadata"] = {
                "num_pages": num_pages,
                "file_size_mb": len(file_content) / (1024 * 1024),
                "title": metadata.get("/Title", "") if metadata else "",
                "author": metadata.get("/Author", "") if metadata else "",
                "creator": metadata.get("/Creator", "") if metadata else ""
            }
            
            # PDF is valid
            result["is_valid"] = True
            logger.file_validation(filename, "passed", f"{num_pages} pages")
            
        except PyPDF2.errors.PdfReadError as e:
            result["errors"].append(f"Invalid PDF structure: {str(e)}")
        except Exception as e:
            result["errors"].append(f"PDF validation failed: {str(e)}")
        
        return result
    
    @staticmethod
    def _validate_image(file_content: bytes, filename: str, file_ext: str) -> Dict[str, any]:
        """
        Validate image file format and integrity
        
        Checks:
        1. File is a valid image
        2. Image can be opened
        3. Image has valid dimensions
        4. Image format matches extension
        """
        result = {
            "is_valid": False,
            "file_type": "image",
            "format": file_ext.upper().replace('.', ''),
            "errors": [],
            "warnings": [],
            "metadata": {}
        }
        
        try:
            # Open image from bytes
            image_stream = io.BytesIO(file_content)
            img = Image.open(image_stream)
            
            # Verify image (loads image data)
            img.verify()
            
            # Re-open for accessing properties (verify() closes the image)
            image_stream.seek(0)
            img = Image.open(image_stream)
            
            # Extract metadata
            width, height = img.size
            result["metadata"] = {
                "width": width,
                "height": height,
                "format": img.format,
                "mode": img.mode,
                "file_size_mb": len(file_content) / (1024 * 1024)
            }
            
            # Validate dimensions
            if width < 100 or height < 100:
                result["warnings"].append(
                    f"Image resolution is very low ({width}x{height}). "
                    "Text extraction quality may be poor."
                )
            
            # Check if format matches extension
            expected_format = file_ext.upper().replace('.', '').replace('JPG', 'JPEG')
            if img.format != expected_format:
                result["warnings"].append(
                    f"File extension is {file_ext} but image format is {img.format}"
                )
            
            # Image is valid
            result["is_valid"] = True
            logger.file_validation(filename, "passed", f"{width}x{height}, {img.format}")
            
        except Image.UnidentifiedImageError:
            result["errors"].append(f"File is not a valid {file_ext.upper()} image")
        except Exception as e:
            result["errors"].append(f"Image validation failed: {str(e)}")
        
        return result
    
    @staticmethod
    def get_validation_summary(validation_result: Dict) -> str:
        """
        Generate human-readable validation summary
        
        Returns:
            String summary of validation results
        """
        if validation_result["is_valid"]:
            summary = f"✅ {validation_result['format']} file is valid\n"
            
            # Add metadata info
            metadata = validation_result["metadata"]
            if validation_result["file_type"] == "pdf":
                summary += f"   - Pages: {metadata.get('num_pages', 0)}\n"
                summary += f"   - Size: {metadata.get('file_size_mb', 0):.2f}MB"
            else:
                summary += f"   - Dimensions: {metadata.get('width', 0)}x{metadata.get('height', 0)}\n"
                summary += f"   - Size: {metadata.get('file_size_mb', 0):.2f}MB"
            
            # Add warnings if any
            if validation_result["warnings"]:
                summary += "\n⚠️  Warnings:\n"
                for warning in validation_result["warnings"]:
                    summary += f"   - {warning}\n"
        else:
            summary = "❌ File validation failed\n"
            for error in validation_result["errors"]:
                summary += f"   - {error}\n"
        
        return summary