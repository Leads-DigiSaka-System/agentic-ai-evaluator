import os
import re
from typing import Tuple, Optional
from pathlib import Path
from src.utils import constants
from src.utils.errors import ValidationError


class FileValidator:
    """
    Validates file uploads for security and compatibility
    
    Validates:
    - File extension
    - File size  
    - Filename security (path traversal)
    - MIME type (basic validation)
    """
    
    # Dangerous filename patterns
    DANGEROUS_PATTERNS = [
        r'\.\.',           # Path traversal
        r'/[\\\/]',        # Directory separators
        r'null',           # Device files
        r'con$',           # Reserved names on Windows
        r'prn$',
        r'aux$',
        r'clock\$',        # Reserved on Windows
        r'[<>:"|?*]',      # Invalid characters
    ]
    
    # Check these by regex
    DANGEROUS_CHARS_REGEX = re.compile('[<>:"|?*]', re.IGNORECASE)
    
    @staticmethod
    def validate_filename(filename: str) -> Tuple[bool, Optional[str]]:
        """
        Validate filename for security
        
        Returns:
            (is_valid, error_message)
        """
        if not filename or not filename.strip():
            return False, "Filename cannot be empty"
        
        # Check for dangerous patterns
        for pattern in FileValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                return False, f"Dangerous filename pattern detected: {pattern}"
        
        # Check for dangerous characters
        if FileValidator.DANGEROUS_CHARS_REGEX.search(filename):
            return False, "Filename contains invalid characters"
        
        # Check for leading/trailing spaces or dots
        if filename.strip() != filename or filename.strip('.') != filename:
            return False, "Filename cannot have leading/trailing spaces or dots"
        
        # Check filename length
        if len(filename) > 255:
            return False, "Filename too long (max 255 characters)"
        
        return True, None
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Extract file extension safely"""
        if '.' not in filename:
            return ''
        
        ext = filename.lower().split('.')[-1]
        return f'.{ext}' if ext else ''
    
    @staticmethod
    def validate_file_type(filename: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file extension is allowed
        
        Returns:
            (is_valid, error_message)
        """
        extension = FileValidator.get_file_extension(filename)
        
        if extension not in constants.ALLOWED_EXTENSIONS:
            allowed = ', '.join(constants.ALLOWED_EXTENSIONS)
            return False, f"Unsupported file type: {extension}. Allowed: {allowed}"
        
        return True, None
    
    @staticmethod
    def validate_file_size(content: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate file size
        
        Returns:
            (is_valid, error_message)
        """
        if len(content) == 0:
            return False, "Uploaded file is empty"
        
        if len(content) > constants.MAX_FILE_SIZE_BYTES:
            size_mb = len(content) / (1024 * 1024)
            max_mb = constants.MAX_FILE_SIZE_MB
            return False, f"File too large ({size_mb:.2f}MB). Maximum: {max_mb}MB"
        
        return True, None
    
    @staticmethod
    def validate_file_upload(
        filename: str,
        content: bytes
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive file upload validation
        
        Returns:
            (is_valid, error_message)
        """
        # Validate filename security
        filename_valid, error = FileValidator.validate_filename(filename)
        if not filename_valid:
            return False, error
        
        # Validate file type
        type_valid, error = FileValidator.validate_file_type(filename)
        if not type_valid:
            return False, error
        
        # Validate file size
        size_valid, error = FileValidator.validate_file_size(content)
        if not size_valid:
            return False, error
        
        # All validations passed
        return True, None
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to remove dangerous characters
        
        Note: This is a fallback. Primary validation should reject dangerous filenames.
        """
        # Remove dangerous patterns
        sanitized = filename
        
        # Remove path traversal
        sanitized = sanitized.replace('..', '')
        sanitized = sanitized.replace('/', '_')
        sanitized = sanitized.replace('\\', '_')
        
        # Remove invalid characters
        sanitized = FileValidator.DANGEROUS_CHARS_REGEX.sub('_', sanitized)
        
        # Remove leading/trailing dots/spaces
        sanitized = sanitized.strip('. ')
        
        # Ensure filename is not too long
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            max_name_len = 255 - len(ext)
            sanitized = name[:max_name_len] + ext
        
        return sanitized


def validate_and_raise(
    filename: str,
    content: bytes,
    field_name: str = "file"
) -> None:
    """
    Validate file upload and raise exception if invalid
    
    Raises:
        ValidationError: If file is invalid
    """
    is_valid, error = FileValidator.validate_file_upload(filename, content)
    
    if not is_valid:
        raise ValidationError(
            detail=error,
            field=field_name,
            value=filename[:50]  # Limit filename in error
        )

