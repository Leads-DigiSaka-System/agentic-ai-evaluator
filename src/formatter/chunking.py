# file: src/formatter/chunking.py
import re
from langchain.text_splitter import SentenceTransformersTokenTextSplitter
from src.utils.config import EMBEDDING_MODEL

def chunk_markdown_safe(markdown_text: str, model=EMBEDDING_MODEL):
    """
    Hybrid chunking:
      - Flatten markdown tables into multi-line text chunks
      - Split remaining text into safe token-based chunks
    """
    try:
        if not markdown_text or not markdown_text.strip():
            raise ValueError("❌ Empty or invalid markdown text provided")

        chunks = []

        # Regex to capture markdown tables
        table_pattern = r"(?:\|.*\|\r?\n?)+"
        tables = re.findall(table_pattern, markdown_text)

        # 1. Flatten each table into one chunk
        for i, table in enumerate(tables):
            rows = [r.strip() for r in table.strip().split("\n") if "|" in r]

            # skip header + separator lines
            clean_rows = [
                r for r in rows
                if not re.match(r'^\|[-\s]+\|$', r) and "---" not in r
            ]

            # convert each row into natural language
            flattened_lines = []
            headers = [h.strip() for h in clean_rows[0].split("|") if h.strip()]
            for row in clean_rows[1:]:
                cols = [c.strip() for c in row.split("|") if c.strip()]
                if len(cols) == len(headers):
                    line = ", ".join(f"{h}: {c}" for h, c in zip(headers, cols))
                    flattened_lines.append(line)

            flat_table_text = "\n".join(flattened_lines)

            if flat_table_text.strip():
                token_count = len(flat_table_text.split())
                chunks.append({
                    "chunk_id": f"table_{i}_flat",
                    "content": flat_table_text,
                    "metadata": {"type": "table_flat"},
                    "token_count": token_count,
                    "char_count": len(flat_table_text)
                })

        # 2. Remove tables from main text
        text_wo_tables = markdown_text
        for t in tables:
            text_wo_tables = text_wo_tables.replace(t, "")

        # 3. Split the remaining text
        splitter = SentenceTransformersTokenTextSplitter(
            model_name=model,
            chunk_size=400,   # safe for e5-base
            chunk_overlap=50
        )
        text_chunks = splitter.split_text(text_wo_tables)

        for i, chunk in enumerate(text_chunks):
            chunks.append({
                "chunk_id": f"text_{i}",
                "content": chunk.strip(),
                "metadata": {"type": "text"},
                "token_count": len(chunk.split()),
                "char_count": len(chunk)
            })

        if not chunks:
            raise RuntimeError("❌ No chunks were created. Check input formatting.")

        print(f"✅ Chunking successful. Total chunks: {len(chunks)}")
        return chunks

    except Exception as e:
        import traceback
        print(f"⚠️ Error during chunking: {str(e)}")
        traceback.print_exc()
        return []
