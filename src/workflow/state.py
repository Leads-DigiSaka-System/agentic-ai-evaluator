from typing import Dict, Any, List, Optional, TypedDict
from src.workflow.models import SimpleStorageApprovalRequest

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
    _tracking_id: Optional[str]
    _user_id: Optional[str]
    """
    User ID for multi-user isolation and tracking.
    Used for:
    - Langfuse user-specific traces
    - Logging with user context
    - Cache isolation (already handled separately)
    - Future user-specific features
    """
    
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
    # NEW: VALIDATION RESULTS
    # ============================================
    
    file_validation: Optional[Dict[str, Any]]
    """
    File format validation results from FileValidator
    {
        "is_valid": bool,
        "file_type": str ("pdf" | "image"),
        "format": str (e.g., "PDF", "PNG"),
        "errors": List[str],
        "warnings": List[str],
        "metadata": Dict (file-specific info like pages, dimensions)
    }
    """
    
    is_valid_content: Optional[bool]
    """
    Flag set by content_validation_node
    True if content is a valid product demo/trial report
    False if content is not a demo (invoice, letter, etc.)
    Router uses this to decide: proceed to analysis OR error out
    """
    
    content_validation: Optional[Dict[str, Any]]
    """
    LLM content validation result
    {
        "is_valid_demo": bool,
        "confidence": float (0.0-1.0),
        "content_type": str ("product_demo" | "trial_report" | "invoice" | etc.),
        "reasoning": str,
        "detected_elements": {
            "has_product_info": bool,
            "has_trial_data": bool,
            "has_numeric_results": bool,
            "has_location_info": bool
        },
        "feedback": str (user-friendly message)
    }
    """
    
    # ============================================
    # INTELLIGENT EVALUATION RESULTS (existing)
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
    # STORAGE CONTROL FLAGS
    # ============================================
    
    storage_approved: Optional[bool]
    """
    User-controlled flag for storage approval
    True: User approved storage, proceed with storing
    False: User rejected storage, skip storing
    None: No user decision yet (default)
    """
    
    storage_prepared: Optional[bool]
    """
    Flag indicating if storage data has been prepared
    Set to True after prepare_storage_data() is called
    """
    
    storage_data: Optional[Dict[str, Any]]
    """
    Prepared storage data from StorageService.prepare_storage_data()
    Contains chunks, analysis_response, metadata, etc.
    """
    
    storage_preview: Optional[Dict[str, Any]]
    """
    Storage preview data for user review
    Contains summary of what would be stored
    """
    
    # ============================================
    # STORAGE APPROVAL REQUEST
    # ============================================
    
    storage_approval_request: Optional[SimpleStorageApprovalRequest]
    """
    Storage approval request from user
    Contains cache_id and approval decision
    """