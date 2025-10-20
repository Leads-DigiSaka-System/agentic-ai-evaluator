# file: src/workflow/state.py
from typing import Dict, Any, List, Optional, TypedDict

class ProcessingState(TypedDict):
    # Input
    file_path: str
    file_name: str
    file_content: bytes
    
    # Processing steps
    extracted_markdown: Optional[str]
    form_type: Optional[str]
    chunks: List[Dict[str, Any]]
    analysis_result: Optional[Dict[str, Any]]
    graph_suggestions: Optional[Dict[str, Any]]
    
    # Metadata
    form_id: str
    metadata: Dict[str, Any]
    insertion_date: str
    
    # Status
    current_step: str
    errors: List[str]
    
    # NEW FIELDS FOR AGENTIC REASONING
    output_evaluation: Optional[Dict[str, Any]]  # For output evaluator
    needs_reanalysis: Optional[bool]  # Flag for re-analysis
    goal_reasoning: Optional[Dict[str, Any]]  # For storing reasoner results