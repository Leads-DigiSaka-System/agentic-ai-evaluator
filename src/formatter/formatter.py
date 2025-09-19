import re

def clean_chunk_text(text: str) -> str:
    # Remove excessive whitespace
    text = text.strip()
    
    # Normalize multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Optional: normalize spaces around pipes in tables
    text = re.sub(r"\s*\|\s*", " | ", text)
    
    return text