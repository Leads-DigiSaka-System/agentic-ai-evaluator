"""
Score normalization utilities for hybrid search fusion.

This module provides utilities for normalizing scores from different retrievers
before combining them in hybrid search scenarios.
"""

from typing import List, Dict, Any, Optional
from langchain_core.documents import Document


def normalize_scores_min_max(scores: List[float]) -> List[float]:
    """
    Normalize scores to [0, 1] range using min-max normalization.
    
    This is useful when combining scores from different retrievers (dense vs sparse)
    that may have different score distributions.
    
    Args:
        scores: List of raw scores to normalize
        
    Returns:
        List of normalized scores in [0, 1] range
        
    Example:
        >>> scores = [0.8, 0.6, 0.4, 0.2]
        >>> normalized = normalize_scores_min_max(scores)
        >>> # All scores now in [0, 1] range
    """
    if not scores:
        return []
    
    min_score = min(scores)
    max_score = max(scores)
    
    # Handle edge case where all scores are the same
    if max_score == min_score:
        return [1.0] * len(scores)
    
    # Normalize: (score - min) / (max - min)
    return [(score - min_score) / (max_score - min_score) for score in scores]


def normalize_scores_z_score(scores: List[float]) -> List[float]:
    """
    Normalize scores using Z-score normalization (standardization).
    
    Converts scores to have mean=0 and std=1, then scales to [0, 1].
    Useful when score distributions are approximately normal.
    
    Args:
        scores: List of raw scores to normalize
        
    Returns:
        List of normalized scores in [0, 1] range
    """
    if not scores:
        return []
    
    import statistics
    
    mean_score = statistics.mean(scores)
    std_score = statistics.stdev(scores) if len(scores) > 1 else 1.0
    
    if std_score == 0:
        return [0.5] * len(scores)  # All same, return middle value
    
    # Z-score: (score - mean) / std
    z_scores = [(score - mean_score) / std_score for score in scores]
    
    # Scale to [0, 1] using min-max on z-scores
    min_z = min(z_scores)
    max_z = max(z_scores)
    
    if max_z == min_z:
        return [0.5] * len(scores)
    
    return [(z - min_z) / (max_z - min_z) for z in z_scores]


def normalize_document_scores(
    documents: List[Document], 
    method: str = "min_max"
) -> List[Document]:
    """
    Normalize scores in a list of Document objects.
    
    Updates the 'score' field in each document's metadata with normalized values.
    Preserves original score in 'original_score' field if not already present.
    
    Args:
        documents: List of Document objects with scores in metadata
        method: Normalization method - "min_max" or "z_score"
        
    Returns:
        List of Document objects with normalized scores
        
    Example:
        >>> docs = [Document(page_content="...", metadata={"score": 0.8})]
        >>> normalized = normalize_document_scores(docs)
        >>> # Scores are now normalized
    """
    if not documents:
        return documents
    
    # Extract scores
    scores = []
    for doc in documents:
        score = doc.metadata.get("score", 0.0)
        if not isinstance(score, (int, float)):
            try:
                score = float(score)
            except (ValueError, TypeError):
                score = 0.0
        scores.append(score)
    
    # Normalize scores
    if method == "min_max":
        normalized_scores = normalize_scores_min_max(scores)
    elif method == "z_score":
        normalized_scores = normalize_scores_z_score(scores)
    else:
        raise ValueError(f"Unknown normalization method: {method}. Use 'min_max' or 'z_score'")
    
    # Update documents with normalized scores
    for doc, norm_score in zip(documents, normalized_scores):
        # Preserve original score if not already stored
        if "original_score" not in doc.metadata:
            doc.metadata["original_score"] = doc.metadata.get("score", 0.0)
        doc.metadata["score"] = norm_score
    
    return documents


def reciprocal_rank_fusion(
    dense_results: List[Document],
    sparse_results: List[Document],
    k: int = 60
) -> List[Document]:
    """
    Combine results from multiple retrievers using Reciprocal Rank Fusion (RRF).
    
    RRF is a rank-based fusion method that doesn't require score normalization.
    It's often more robust than score-based fusion when scores have different scales.
    
    Formula: RRF_score = sum(1 / (k + rank)) for each retriever
    
    Args:
        dense_results: Results from dense retriever
        sparse_results: Results from sparse retriever
        k: RRF constant (typically 60) - higher = more weight on top ranks
        
    Returns:
        Combined and ranked list of unique documents
        
    Example:
        >>> dense = [doc1, doc2]
        >>> sparse = [doc2, doc3]
        >>> combined = reciprocal_rank_fusion(dense, sparse)
        >>> # doc2 appears in both, so it gets higher RRF score
    """
    from collections import defaultdict
    
    # Track RRF scores by document ID
    rrf_scores = defaultdict(float)
    doc_map = {}  # Map ID to document
    
    # Process dense results
    for rank, doc in enumerate(dense_results, start=1):
        doc_id = doc.metadata.get("id", str(id(doc)))
        rrf_scores[doc_id] += 1.0 / (k + rank)
        doc_map[doc_id] = doc
        doc.metadata["retriever_type"] = "dense"
    
    # Process sparse results
    for rank, doc in enumerate(sparse_results, start=1):
        doc_id = doc.metadata.get("id", str(id(doc)))
        rrf_scores[doc_id] += 1.0 / (k + rank)
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
            doc.metadata["retriever_type"] = "sparse"
        else:
            # Document appears in both - mark as hybrid
            doc_map[doc_id].metadata["retriever_type"] = "hybrid"
    
    # Sort by RRF score (descending)
    sorted_docs = sorted(
        doc_map.values(),
        key=lambda d: rrf_scores[d.metadata.get("id", str(id(d)))],
        reverse=True
    )
    
    # Update metadata with RRF scores
    for doc in sorted_docs:
        doc_id = doc.metadata.get("id", str(id(doc)))
        doc.metadata["rrf_score"] = rrf_scores[doc_id]
        doc.metadata["score"] = rrf_scores[doc_id]  # Use RRF score as main score
    
    return sorted_docs

