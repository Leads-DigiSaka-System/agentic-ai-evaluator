# file: src/workflow/state.py
from typing import Dict, Any, List, Optional, TypedDict

class ProcessingState(TypedDict):
    """
    State for agricultural data processing workflow
    
    Philosophy:
    - Quality flags (needs_reanalysis, needs_regraph) are set by INTELLIGENT evaluation
    - Workflow routing is DETERMINISTIC based on these flags
    - This separates "quality assessment" from "flow control"
    """
    
    # ============================================
    # INPUT DATA
    # ============================================
    file_path: str
    file_name: str
    file_content: bytes
    
    # ============================================
    # PROCESSING OUTPUTS
    # ============================================
    extracted_markdown: Optional[str]
    form_type: Optional[str]
    analysis_result: Optional[Dict[str, Any]]
    graph_suggestions: Optional[Dict[str, Any]]
    chunks: List[Dict[str, Any]]
    
    # ============================================
    # METADATA
    # ============================================
    form_id: str
    metadata: Dict[str, Any]
    insertion_date: str
    
    # ============================================
    # WORKFLOW CONTROL
    # ============================================
    current_step: str  # Tracks current processing stage
    errors: List[str]  # Accumulated errors
    
    # ============================================
    # INTELLIGENT EVALUATION RESULTS
    # These flags are set by LLM-based quality assessment
    # The router respects these flags for retry logic
    # ============================================
    
    output_evaluation: Optional[Dict[str, Any]]
    """
    LLM evaluation result containing:
    - confidence: float (0.0-1.0)
    - feedback: str
    - decision: str ("store", "re_analyze", "suggest_graphs")
    - issue_type: str ("fixable_analysis", "graph_issue", "source_limitation", "no_issue")
    """
    
    needs_reanalysis: Optional[bool]
    """
    Flag set by evaluation_node when analysis quality is insufficient
    Router checks this to decide: proceed to graphs OR retry analysis
    """
    
    needs_regraph: Optional[bool]
    """
    Flag set by evaluation_node when graph quality is insufficient
    Router checks this to decide: proceed to chunk OR retry graph generation
    """
    
    evaluation_attempts: Optional[int]
    """
    Counter for retry attempts (prevents infinite loops)
    Resets when moving to next major stage
    """
    
    last_evaluation_summary: Optional[Dict[str, Any]]
    """
    Quick reference for last evaluation decision
    Useful for debugging and monitoring
    """
    
    # ============================================
    # DEPRECATED / UNUSED
    # ============================================
    # goal_reasoning: Optional[Dict[str, Any]]  
    # ☝️ No longer used - we don't use LLM for routing decisions