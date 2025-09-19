# file: src/generator/embedding.py
from src.generator.model_loader import load_embedding_model

def embed_chunks(chunks):
    """
    Embed a list of chunks using HuggingFaceEmbeddings.
    Batch embeds for speed.
    """
    try:
        model = load_embedding_model()

        contents = [ch["content"] for ch in chunks]
        if not contents:
            raise ValueError("❌ No chunks provided for embedding")

        # Use embed_documents instead of embed
        embeddings = model.embed_documents(contents)

        embedded = []
        for ch, emb in zip(chunks, embeddings):
            embedded.append({
                **ch,
                "embedding": emb
            })

        print(f"✅ Embedding successful. Total chunks embedded: {len(embedded)}")
        return embedded

    except Exception as e:
        import traceback
        print(f"⚠️ Error during embedding: {str(e)}")
        traceback.print_exc()
        return []
