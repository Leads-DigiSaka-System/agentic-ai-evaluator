# file: src/formatter/chunking.py
import re
from langchain.text_splitter import SentenceTransformersTokenTextSplitter
from src.core.config import EMBEDDING_MODEL
from src.shared.logging.clean_logger import get_clean_logger

def chunk_markdown_safe(markdown_text: str, model=EMBEDDING_MODEL):
    """
    Hybrid chunking:
      - Flatten markdown tables into multi-line text chunks
      - Split remaining text into safe token-based chunks (NO OVERLAP)
    """
    logger = get_clean_logger(__name__)
    
    try:
        if not markdown_text or not markdown_text.strip():
            raise ValueError("Empty or invalid markdown text provided")

        chunks = []

        # Regex to capture markdown tables (improved pattern)
        table_pattern = r"(?:\|.*?\|(?:\r?\n|$))+"
        
        # Find all tables with their positions
        table_matches = list(re.finditer(table_pattern, markdown_text))
        tables = [m.group() for m in table_matches]
        
        logger.chunking_start("markdown", len(markdown_text))

        # 1. Flatten each table into one chunk
        for i, table in enumerate(tables):
            rows = [r.strip() for r in table.strip().split("\n") if "|" in r]

            # skip header + separator lines
            clean_rows = [
                r for r in rows
                if not re.match(r'^\|[-\s:]+\|$', r) and "---" not in r
            ]

            if len(clean_rows) < 2:  # Need at least header + 1 data row
                logger.warning(f"Skipping table {i} - insufficient rows")
                continue

            # convert each row into natural language
            flattened_lines = []
            headers = [h.strip() for h in clean_rows[0].split("|") if h.strip()]
            
            for row_idx, row in enumerate(clean_rows[1:], start=1):
                cols = [c.strip() for c in row.split("|") if c.strip()]
                if len(cols) == len(headers):
                    line = ", ".join(f"{h}: {c}" for h, c in zip(headers, cols))
                    flattened_lines.append(line)
                else:
                    logger.warning(f"Table {i}, Row {row_idx}: Column mismatch ({len(cols)} vs {len(headers)})")

            flat_table_text = "\n".join(flattened_lines)

            if flat_table_text.strip():
                token_count = len(flat_table_text.split())
                chunks.append({
                    "chunk_id": f"table_{i}_flat",
                    "content": flat_table_text,
                    "metadata": {
                        "type": "table_flat",
                        "table_index": i,
                        "row_count": len(flattened_lines)
                    },
                    "token_count": token_count,
                    "char_count": len(flat_table_text)
                })
                logger.chunking_result(1, token_count, f"Table {i} flattened: {len(flattened_lines)} rows")

        # 2. Remove tables from main text (improved removal)
        text_wo_tables = markdown_text
        
        # Sort matches by position (reverse order to maintain indices)
        for match in sorted(table_matches, key=lambda m: m.start(), reverse=True):
            start, end = match.span()
            text_wo_tables = text_wo_tables[:start] + text_wo_tables[end:]
        
        # Clean up extra whitespace
        text_wo_tables = re.sub(r'\n{3,}', '\n\n', text_wo_tables).strip()
        
        logger.info(f"Text without tables: {len(text_wo_tables)} chars")

        # 3. Split the remaining text with NO OVERLAP
        if text_wo_tables.strip():
            splitter = SentenceTransformersTokenTextSplitter(
                model_name=model,
                chunk_size=400,
                chunk_overlap=0  # ✅ NO OVERLAP = NO DUPLICATES!
            )
            text_chunks = splitter.split_text(text_wo_tables)

            for i, chunk in enumerate(text_chunks):
                chunk_text = chunk.strip()
                if chunk_text:  # Only add non-empty chunks
                    chunks.append({
                        "chunk_id": f"text_{i}",
                        "content": chunk_text,
                        "metadata": {
                            "type": "text",
                            "chunk_index": i
                        },
                        "token_count": len(chunk_text.split()),
                        "char_count": len(chunk_text)
                    })
            
            logger.chunking_result(len(text_chunks), sum(len(chunk.split()) for chunk in text_chunks), "Text split with no overlap")
        else:
            logger.warning("No text content after removing tables")

        if not chunks:
            raise RuntimeError("No chunks were created. Check input formatting.")

        # Deduplicate chunks based on content
        unique_chunks = []
        seen_content = set()
        
        for chunk in chunks:
            content_hash = hash(chunk["content"][:100])  # Hash first 100 chars
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_chunks.append(chunk)
            else:
                logger.warning(f"Skipped duplicate chunk: {chunk['chunk_id']}")
        
        logger.chunking_result(len(unique_chunks), sum(chunk.get('token_count', 0) for chunk in unique_chunks), "Chunking successful")
        return unique_chunks

    except Exception as e:
        import traceback
        logger.chunking_error(str(e))
        traceback.print_exc()
        return []