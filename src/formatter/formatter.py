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
    Extract ONLY the first # header from markdown content
    """
    # Hanapin lang yung VERY FIRST # header
    first_heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if first_heading_match:
        return first_heading_match.group(1).strip()
    
    # Kung wala talagang # header, return simple unknown
    return "Unknown Form"
