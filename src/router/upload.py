# file: pdf_extract_router.py (updated)
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse
from src.Upload.form_extractor import extract_pdf_with_gemini
from src.formatter.chunking import chunk_markdown_safe
from src.generator.embedding import embed_chunks
from src.database.insert import qdrant_client  # NEW IMPORT
import os
import tempfile

router = APIRouter()

@router.post("/upload-file-product-demo", response_class=PlainTextResponse)
async def upload_file(file: UploadFile = File(...)) -> str:
    """
    Extract content from uploaded PDF using Gemini API, run hybrid chunking,
    embed the chunks, upload to Qdrant, and return the extracted markdown.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed for extraction."
        )

    tmp_path = None
    try:
        # Save uploaded PDF to temp file
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Step 1: Extract Markdown
        extracted_content = extract_pdf_with_gemini(tmp_path)
        if not extracted_content:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract content from PDF"
            )

        # Step 2: Hybrid chunking
        chunks = chunk_markdown_safe(extracted_content)

        # Step 3: Embedding (batch mode)
        embedded_chunks = embed_chunks(chunks)

        # 🔍 Print chunk + embedding info
        if embedded_chunks:
            print("\n📊 CHUNKING & EMBEDDING SUMMARY")
            print("-" * 80)
            print(f"Total chunks created: {len(embedded_chunks)}")
            avg_tokens = sum(c['token_count'] for c in embedded_chunks) / len(embedded_chunks)
            print(f"Average chunk size: {avg_tokens:.1f} tokens")

            # Step 4: NEW - Insert into Qdrant
            print("\n📦 Inserting into Qdrant...")
            insert_success = qdrant_client.insert_chunks(embedded_chunks)
            
            if insert_success:
                print("✅ Successfully stored in vector database")
            else:
                print("❌ Failed to store in vector database")

        else:
            print("⚠️ No chunks were generated/embedded from this document.")

        # Return the extracted markdown
        return extracted_content

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass