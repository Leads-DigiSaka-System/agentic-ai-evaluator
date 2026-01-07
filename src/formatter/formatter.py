import re

def clean_chunk_text(text: str) -> str:
    # Remove excessive whitespace
    text = text.strip()
    
    # Normalize multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Optional: normalize spaces around pipes in tables
    text = re.sub(r"\s*\|\s*", " | ", text)
    
    return text

def extract_form_type_from_content(content: str) -> str:
    """
    Extract the form type from the extracted markdown content.
    
    The form type should be the first # header in the markdown, which should be
    the actual form title extracted from the document (e.g., "Leads Agri Foliar/Biostimulant Demo Form").
    
    The extraction prompt is configured to extract the actual form title from the document
    and use it as the main header, so this function simply extracts that header.
    
    Args:
        content: The extracted markdown content from the form
        
    Returns:
        The form type/title as a string, or "Unknown Form" if no header is found
    """
    # Extract the first # header (should be the form title)
    first_heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if first_heading_match:
        form_type = first_heading_match.group(1).strip()
        # Remove any placeholder text or generic titles if they somehow got through
        if "Agricultural Demo Form Extraction" in form_type:
            # Try to find actual form title elsewhere in content
            # Look for common form title patterns
            form_title_patterns = [
                r'Leads Agri\s+[A-Za-z/]+ Demo Form',
                r'[A-Za-z\s]+Demo Form',
                r'[A-Za-z\s]+Trial Form'
            ]
            for pattern in form_title_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(0).strip()
        return form_type
    
    # Fallback: Try to find form title patterns in the content
    form_title_patterns = [
        r'Leads Agri\s+[A-Za-z/]+ Demo Form',
        r'[A-Za-z\s]+Demo Form',
        r'[A-Za-z\s]+Trial Form'
    ]
    for pattern in form_title_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    # If no form title found, return unknown
    return "Unknown Form"
