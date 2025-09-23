from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from src.database.hybrid_search import create_hybrid_search
from src.utils.prompt_template import synthesizer_template
from langchain_core.prompts import PromptTemplate
from src.utils.llm_helper import invoke_llm

router = APIRouter()

# Initialize hybrid search once
hybrid_search = create_hybrid_search()

class PipelineRequest(BaseModel):
    query: str
    top_k: int = 5

@router.post("/full_pipeline")   
def full_pipeline(request: PipelineRequest) -> Dict[str, Any]:
    """
    Perform search + retrieve + synthesize using LLM.
    """
    query = request.query
    top_k = request.top_k

    # 1. Retrieve
    results = hybrid_search.search(query=query, top_k=top_k)

    # 2. Build synthesizer prompt
    retrieved_context = "\n\n".join([r["content"] for r in results])
    chunk_count = len(results)

    template: PromptTemplate = synthesizer_template()
    final_prompt = template.format(
        retrieved_context=retrieved_context,
        user_query=query,
        chunk_count=chunk_count
    )

    # 3. Call LLM
    llm_response = invoke_llm(final_prompt)

    # 4. Return results + AI output
    return {
        "synthesized_output": llm_response  # already a string
    }
