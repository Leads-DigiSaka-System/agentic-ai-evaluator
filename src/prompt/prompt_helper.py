from langchain.prompts import PromptTemplate

# Query Rewriting Template
def query_rewrite_template():
    return PromptTemplate.from_template(
"""Improve the following search query for better vector database retrieval. 
Consider synonyms, context, and agricultural terminology.

Original Query: {original_query}

Improved Query:"""
)

