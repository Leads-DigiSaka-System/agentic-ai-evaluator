from langgraph.graph import StateGraph, END
from src.workflow.state import ProcessingState
from src.workflow.nodes.nodes import extraction_node, analysis_node, chunking_node, storage_node, error_node
from src.workflow.nodes.graph_suggestion_node import graph_suggestion_node
from src.workflow.nodes.evaluation_node import evaluation_node
from src.workflow.nodes.validation_node import content_validation_node


def create_advanced_processing_workflow():
    """
    Create workflow with CONTENT VALIDATION + INTELLIGENT EVALUATION
    
    NEW: Added content_validation node after extraction
    
    Flow:
    1. Extract (with file format validation)
    2. Validate Content (LLM checks if it's a product demo)
    3. Analyze (existing)
    4. Evaluate Analysis (existing)
    5. Suggest Graphs (existing)
    6. Evaluate Graphs (existing)
    7. Chunk (existing)
    8. Store (existing)
    """
    workflow = StateGraph(ProcessingState)
    
    # Add all nodes
    workflow.add_node("extract", extraction_node)
    workflow.add_node("validate_content", content_validation_node)  # NEW
    workflow.add_node("analyze", analysis_node)
    workflow.add_node("evaluate_analysis", evaluation_node)
    workflow.add_node("suggest_graphs", graph_suggestion_node)
    workflow.add_node("evaluate_graphs", evaluation_node)
    workflow.add_node("chunk", chunking_node)
    workflow.add_node("store", storage_node)
    workflow.add_node("handle_errors", error_node)
    
    # Set entry point
    workflow.set_entry_point("extract")
    
    # ============================================
    # ROUTERS WITH NEW VALIDATION LOGIC
    # ============================================
    
    def route_after_extract(state: ProcessingState) -> str:
        """
        After extraction, check for errors then validate content
        
        NEW: Routes to content validation instead of directly to analysis
        """
        if state.get("errors") and not state.get("extracted_markdown"):
            print("❌ Extraction failed critically")
            return "handle_errors"
        
        # Check file validation results (if available)
        file_validation = state.get("file_validation", {})
        if file_validation and not file_validation.get("is_valid", True):
            print("❌ File format validation failed")
            return "handle_errors"
        
        print("✅ Extract → Validate Content")
        return "validate_content"
    
    def route_after_content_validation(state: ProcessingState) -> str:
        """
        NEW ROUTER: After content validation, proceed to analysis or error
        
        Checks if content is a valid product demo
        """
        is_valid = state.get("is_valid_content", False)
        validation_result = state.get("content_validation", {})
        
        if not is_valid:
            confidence = validation_result.get("confidence", 0.0)
            content_type = validation_result.get("content_type", "unknown")
            print(f"❌ Content validation failed: {content_type} (confidence: {confidence:.2f})")
            print(f"📝 Feedback: {validation_result.get('feedback', 'No feedback')}")
            return "handle_errors"
        
        print(f"✅ Content validated as product demo → Analyze")
        return "analyze"
    
    def route_after_analysis(state: ProcessingState) -> str:
        """After analysis, check for errors then proceed to evaluation"""
        if state.get("errors") and not state.get("analysis_result"):
            print("❌ Analysis failed critically")
            return "handle_errors"
        print("✅ Analyze → Evaluate Analysis")
        return "evaluate_analysis"
    
    def route_after_analysis_evaluation(state: ProcessingState) -> str:
        """
        INTELLIGENT ROUTING based on evaluation results
        """
        needs_reanalysis = state.get("needs_reanalysis", False)
        evaluation = state.get("output_evaluation", {})
        attempts = state.get("evaluation_attempts", 0)
        
        # Handle list returns from LLM
        if isinstance(evaluation, list):
            evaluation = evaluation[0] if evaluation else {}
        
        issue_type = evaluation.get("issue_type", "no_issue")
        confidence = evaluation.get("confidence", 0.5)
        
        # INTELLIGENT DECISION LOGIC
        if needs_reanalysis and attempts < 2:
            print(f"🔄 Analysis quality low (confidence: {confidence:.2f}) - Retrying analysis (attempt {attempts + 1})")
            return "analyze"
        
        if issue_type == "source_limitation":
            print("✅ Source limitations identified (expected) - Proceeding to graphs")
            return "suggest_graphs"
        
        if confidence < 0.3 and attempts < 2:
            print(f"⚠️ Very low confidence ({confidence:.2f}) - Forcing reanalysis")
            state["needs_reanalysis"] = True
            return "analyze"
        
        # Default: proceed to next step
        print(f"✅ Analysis acceptable (confidence: {confidence:.2f}) → Suggest Graphs")
        return "suggest_graphs"
    
    def route_after_graph_suggestion(state: ProcessingState) -> str:
        """After graph generation, always evaluate graphs"""
        if state.get("errors") and not state.get("graph_suggestions"):
            print("❌ Graph generation failed critically")
            return "handle_errors"
        print("✅ Suggest Graphs → Evaluate Graphs")
        return "evaluate_graphs"
    
    def route_after_graph_evaluation(state: ProcessingState) -> str:
        """
        INTELLIGENT ROUTING based on graph evaluation
        """
        needs_regraph = state.get("needs_regraph", False)
        evaluation = state.get("output_evaluation", {})
        attempts = state.get("evaluation_attempts", 0)
        
        # Handle list returns
        if isinstance(evaluation, list):
            evaluation = evaluation[0] if evaluation else {}
        
        issue_type = evaluation.get("issue_type", "no_issue")
        confidence = evaluation.get("confidence", 0.5)
        
        # INTELLIGENT DECISION LOGIC
        if needs_regraph and attempts < 2:
            print(f"🔄 Graph quality low (confidence: {confidence:.2f}) - Regenerating graphs (attempt {attempts + 1})")
            return "suggest_graphs"
        
        if issue_type == "graph_issue" and confidence < 0.5 and attempts < 2:
            print(f"⚠️ Graph issues detected (confidence: {confidence:.2f}) - Forcing regeneration")
            state["needs_regraph"] = True
            return "suggest_graphs"
        
        # Default: proceed to chunking
        print(f"✅ Graphs acceptable (confidence: {confidence:.2f}) → Chunk")
        return "chunk"
    
    def route_after_chunk(state: ProcessingState) -> str:
        """After chunking, always proceed to storage"""
        if not state.get("chunks"):
            print("❌ Chunking produced no chunks")
            return "handle_errors"
        print(f"✅ Chunk ({len(state.get('chunks', []))} chunks) → Store")
        return "store"
    
    def route_after_store(state: ProcessingState) -> str:
        """After storage, check success then END"""
        if state.get("form_id"):
            print("✅ Storage successful → END")
            return END
        else:
            print("❌ Storage failed")
            return "handle_errors"
    
    # ============================================
    # WORKFLOW EDGES - Updated with Validation
    # ============================================
    
    # Extract → Validate Content (NEW)
    workflow.add_conditional_edges(
        "extract",
        route_after_extract,
        {
            "validate_content": "validate_content",
            "handle_errors": "handle_errors"
        }
    )
    
    # Validate Content → Analyze (NEW)
    workflow.add_conditional_edges(
        "validate_content",
        route_after_content_validation,
        {
            "analyze": "analyze",
            "handle_errors": "handle_errors"
        }
    )
    
    # Analyze → Evaluate Analysis
    workflow.add_conditional_edges(
        "analyze",
        route_after_analysis,
        {
            "evaluate_analysis": "evaluate_analysis",
            "handle_errors": "handle_errors"
        }
    )
    
    # Evaluate Analysis → Suggest Graphs OR Retry Analysis
    workflow.add_conditional_edges(
        "evaluate_analysis",
        route_after_analysis_evaluation,
        {
            "suggest_graphs": "suggest_graphs",
            "analyze": "analyze",
            "handle_errors": "handle_errors"
        }
    )
    
    # Suggest Graphs → Evaluate Graphs
    workflow.add_conditional_edges(
        "suggest_graphs",
        route_after_graph_suggestion,
        {
            "evaluate_graphs": "evaluate_graphs",
            "handle_errors": "handle_errors"
        }
    )
    
    # Evaluate Graphs → Chunk OR Retry Graphs
    workflow.add_conditional_edges(
        "evaluate_graphs",
        route_after_graph_evaluation,
        {
            "chunk": "chunk",
            "suggest_graphs": "suggest_graphs",
            "handle_errors": "handle_errors"
        }
    )
    
    # Chunk → Store
    workflow.add_conditional_edges(
        "chunk",
        route_after_chunk,
        {
            "store": "store",
            "handle_errors": "handle_errors"
        }
    )
    
    # Store → END
    workflow.add_conditional_edges(
        "store",
        route_after_store,
        {
            END: END,
            "handle_errors": "handle_errors"
        }
    )
    
    # Handle errors always ends
    workflow.add_edge("handle_errors", END)
    
    return workflow.compile()

# Create workflow instance
processing_workflow = create_advanced_processing_workflow()