# file: src/generator/embedding.py
from src.generator.model_loader import load_embedding_model
from src.utils.clean_logger import get_clean_logger

def embed_chunks(chunks):
    """
    Embed a list of chunks using HuggingFaceEmbeddings.
    Batch embeds for speed.
    """
    logger = get_clean_logger(__name__)
    
    try:
        model = load_embedding_model()

        contents = [ch["content"] for ch in chunks]
        if not contents:
            raise ValueError("No chunks provided for embedding")

        # Use embed_documents instead of embed
        embeddings = model.embed_documents(contents)

        embedded = []
        for ch, emb in zip(chunks, embeddings):
            embedded.append({
                **ch,
                "embedding": emb
            })

        logger.embedding_result(len(embedded), len(chunks))
        return embedded

    except Exception as e:
        import traceback
        logger.embedding_error(str(e))
        traceback.print_exc()
        return []
