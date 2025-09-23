from typing import List, Any
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from qdrant_client.http import models
from pydantic import Field

class QdrantDenseRetriever(BaseRetriever):
    """
    Custom dense vector retriever for Qdrant that performs semantic similarity search.
    
    This retriever converts text queries into dense vectors (embeddings) and searches
    for semantically similar documents in the Qdrant vector database.
    
    Dense vectors are good at understanding:
    - Synonyms ("car" and "automobile")
    - Context and meaning
    - Conceptual relationships
    """
    
    # Define these as Pydantic fields
    client: Any = Field(description="Qdrant client instance")
    collection_name: str = Field(description="Name of the Qdrant collection")
    dense_encoder: Any = Field(description="Encoder for creating dense vectors")
    vector_name: str = Field(description="Name of the dense vector field in Qdrant")
    search_limit: int = Field(default=10, description="Maximum number of results to retrieve")
    
    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True  # Allow non-Pydantic types like Qdrant client
    
    def _get_relevant_documents(
        self, 
        query: str, 
        *, 
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Retrieve documents using dense vector similarity search.
        
        Process:
        1. Convert the text query into a dense vector using the encoder
        2. Search Qdrant for vectors with high cosine similarity
        3. Convert results to LangChain Document format
        
        Args:
            query: The search query text
            run_manager: LangChain callback manager (for logging/tracing)
            
        Returns:
            List of LangChain Document objects with content and metadata
        """
        try:
            # Step 1: Encode query to dense vector
            # This converts text like "user registration" into a 768-dimensional vector
            dense_vec = self.dense_encoder.encode([query])[0]
            
            # Step 2: Search Qdrant using vector similarity
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=models.NamedVector(
                    name=self.vector_name,
                    vector=dense_vec
                ),
                limit=self.search_limit,
                with_payload=True  # Include document metadata
            )
            
            # Step 3: Convert to LangChain Documents
            documents = []
            for result in results:
                doc = Document(
                    page_content=result.payload.get("content", ""),
                    metadata={
                        "id": result.id,
                        "score": result.score,
                        "retriever_type": "dense",  # Track which retriever found this
                        "form_id": result.payload.get("form_id", ""),
                        "form_title": result.payload.get("form_title", ""),
                        "form_type": result.payload.get("form_type", ""),
                        "date_of_insertion": result.payload.get("date_of_insertion", "")
                    }
                )
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            # Log error and return empty list to prevent crashes
            if run_manager:
                run_manager.on_retriever_error(e)
            print(f"Error in dense retrieval: {e}")
            return []
    
    def update_search_limit(self, new_limit: int):
        """
        Update the maximum number of results to retrieve.
        
        Args:
            new_limit: New limit for search results
        """
        self.search_limit = new_limit
    
    def get_encoder_info(self) -> dict:
        """
        Get information about the dense encoder being used.
        
        Returns:
            Dictionary with encoder information
        """
        return {
            "encoder_type": type(self.dense_encoder).__name__,
            "vector_name": self.vector_name,
            "search_limit": self.search_limit
        }