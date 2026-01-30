# file: src/router/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from fastapi.responses import PlainTextResponse
from src.ingestion.form_extractor import extract_pdf_with_gemini
from src.formatter.chunking import chunk_markdown_safe
from src.formatter.formatter import extract_form_type_from_content
from src.infrastructure.vector_store.insert import qdrant_client
from src.shared.logging.clean_logger import get_clean_logger
from src.monitoring.session.langfuse_session_helper import generate_session_id, propagate_session_id
from src.monitoring.trace.langfuse_helper import is_langfuse_enabled
from typing import Optional
import os
import tempfile
import uuid
from datetime import datetime

if is_langfuse_enabled():
    from langfuse import observe, get_client
else:
    def observe(**kwargs):
        def decorator(fn):
            return fn
        return decorator
    def get_client():
        return None

router = APIRouter()
logger = get_clean_logger(__name__)


@router.post("/upload-file-product-demo", response_class=PlainTextResponse)
@observe(name="upload_file_product_demo")
async def upload_file(
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> str:
    tmp_path = None
    session_id = generate_session_id(prefix="upload_product_demo")
    user_id_val = (x_user_id and x_user_id.strip())[:200] if x_user_id and x_user_id.strip() else ""

    with propagate_session_id(session_id, user_id=user_id_val or None):
        langfuse = get_client() if is_langfuse_enabled() else None
        if langfuse:
            try:
                attrs = {"session_id": session_id, "tags": ["upload", "api", "product_demo"]}
                if user_id_val:
                    attrs["user_id"] = user_id_val
                langfuse.update_current_trace(**attrs)
            except Exception:
                pass
        try:
            # Step 0: Save uploaded PDF
            content = await file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name

            # Step 1: Extract Markdown content
            extracted_content = extract_pdf_with_gemini(tmp_path)
            if not extracted_content:
                raise HTTPException(status_code=500, detail="Failed to extract content from PDF")

            # Step 2: Extract Form Type (first header only)
            form_type = extract_form_type_from_content(extracted_content)
            logger.file_upload(file.filename, len(content))

            # Step 3: Chunking
            chunks = chunk_markdown_safe(extracted_content)
            if not chunks:
                raise HTTPException(status_code=500, detail="No chunks extracted from PDF")

            # Step 4: Attach metadata only (vectors will be handled in insert.py)
            form_id = str(uuid.uuid4())
            insertion_date = datetime.now().isoformat()

            for ch in chunks:
                ch["metadata"] = {
                    "form_id": form_id,
                    "form_title": file.filename,
                    "form_type": form_type,
                    "date_of_insertion": insertion_date,
                }

            logger.file_extraction(file.filename, "markdown", len(extracted_content))

            # Step 5: Insert into Qdrant
            if chunks:
                insert_success = qdrant_client.insert_chunks(chunks)
                if insert_success:
                    logger.storage_success("chunk insertion", len(chunks), f"file: {file.filename}")

            return extracted_content

        except Exception as e:
            logger.file_error(file.filename, str(e))
            raise
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
