import pathlib
from typing import Optional
from google import genai
from google.genai import types
from src.utils.config import GOOGLE_API_KEY, GEMINI_MODEL
from langchain.document_loaders import PyMuPDFLoader
from src.utils.prompt_template import formatting_template
from typing import Dict, Any
import os
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def extract_pdf_with_gemini(pdf_path: str) -> Optional[str]:
    """
    Extract and process PDF using Gemini API with dynamic formatting
    """
    try:
        print(f"Starting Gemini PDF extraction for {pdf_path}...")
        
        # Initialize Gemini client (SAME AS gemini_extractor.py)
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        filepath = pathlib.Path(pdf_path)
        if not filepath.exists():
            print(f"Error: File {pdf_path} not found")
            return None
            
        # Read PDF file
        pdf_data = filepath.read_bytes()
        file_size = len(pdf_data)
        print(f"File size: {file_size / (1024*1024):.2f} MB")

        # Get dynamic extraction prompt (FIXED TEMPLATE USAGE)
        prompt_template = formatting_template()
        extraction_prompt = prompt_template.template
        
        # Process based on file size (SAME APPROACH AS gemini_extractor.py)
        if file_size < 20 * 1024 * 1024:  # 20MB
            print("Processing with inline method...")
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(
                        data=pdf_data,
                        mime_type='application/pdf',
                    ),
                    extraction_prompt
                ]
            )
        else:
            print("Processing with File API method...")
            sample_file = client.files.upload(file=filepath)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[sample_file, extraction_prompt]
            )
        
        # Extract text directly (SAME AS gemini_extractor.py)
        if response.candidates and response.candidates[0].content.parts:
            extracted_text = "".join(part.text for part in response.candidates[0].content.parts)
            print("✅ PDF extraction completed successfully")
            return extracted_text
        else:
            print("❌ No content extracted from response")
            return None

    except Exception as e:
        print(f"❌ Failed to extract text from {pdf_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None



def extract_pdf_metadata(pdf_path: str) -> Dict[str, Any]:
    """Extract metadata from PDF using PyMuPDFLoader"""
    try:
        loader = PyMuPDFLoader(pdf_path)
        document = loader.load([0])[0]  # First page only for metadata
        return document.metadata
    except Exception as e:
        # Return minimal metadata on error
        return {"error": str(e), "source": pdf_path}