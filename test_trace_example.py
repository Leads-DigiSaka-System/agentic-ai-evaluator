"""
Example: Complete Trace with Multiple LLM Generations

This script simulates what happens in a real workflow run.
It creates a trace and adds multiple LLM generations to show
what you'll see in the Langfuse dashboard.
"""

from src.utils.langfuse_helper import (
    init_langfuse,
    create_trace,
    create_trace_id,
    get_langfuse_handler,
    flush_langfuse
)
from src.utils.llm_helper import invoke_llm
import time

def create_example_trace():
    """
    Create an example trace showing what happens in a real workflow
    """
    print("=" * 80)
    print("📊 CREATING EXAMPLE TRACE (Simulating Workflow)")
    print("=" * 80)
    
    # Initialize
    print("\n1️⃣ Initializing Langfuse...")
    client = init_langfuse()
    if not client:
        print("❌ Langfuse not initialized - check your API keys!")
        return
    
    print("✅ Langfuse initialized")
    
    # Create trace (like in multiple_handler.py)
    print("\n2️⃣ Creating workflow trace...")
    trace_id = create_trace_id()
    trace = create_trace(
        name="process_single_report",
        trace_id=trace_id,
        metadata={
            "file_name": "example_report.pdf",
            "file_type": "pdf",
            "workflow_type": "single_report_direct",
            "example": True
        }
    )
    
    if not trace:
        print("❌ Failed to create trace")
        return
    
    print(f"✅ Trace created: process_single_report")
    print(f"   Trace ID: {trace_id}")
    
    # Simulate workflow: Multiple LLM calls (like real workflow)
    print("\n3️⃣ Simulating workflow LLM calls...")
    
    # Generation 1: Content Validation (like validation_node.py)
    print("\n   📝 Generation 1: Content Validation")
    result1 = invoke_llm(
        "Is this a product demo trial? Answer: Yes",
        as_json=True,
        trace_id=trace_id,
        generation_name="content_validation",
        metadata={"step": "content_validation", "node": "validation_node"}
    )
    print(f"   ✅ Result: {result1}")
    
    time.sleep(0.5)  # Simulate processing time
    
    # Generation 2: Analysis (like analysis.py)
    print("\n   📝 Generation 2: Agricultural Analysis")
    result2 = invoke_llm(
        "Analyze this agricultural demo data: Control=50, Treatment=75",
        as_json=True,
        trace_id=trace_id,
        generation_name="agricultural_analysis",
        metadata={"step": "analysis", "node": "analysis_node"}
    )
    print(f"   ✅ Result: {result2}")
    
    time.sleep(0.5)
    
    # Generation 3: Graph Suggestion (like graph_suggestion_node.py)
    print("\n   📝 Generation 3: Graph Suggestion")
    result3 = invoke_llm(
        "Suggest charts for performance comparison data",
        as_json=True,
        trace_id=trace_id,
        generation_name="graph_suggestion",
        metadata={"step": "graph_suggestion", "node": "graph_suggestion_node"}
    )
    print(f"   ✅ Result: {result3}")
    
    time.sleep(0.5)
    
    # Generation 4: Evaluation (like output_evaluator.py)
    print("\n   📝 Generation 4: Output Evaluation (Analysis)")
    result4 = invoke_llm(
        "Evaluate the quality of this analysis. Answer: Good, confidence 0.85",
        as_json=True,
        trace_id=trace_id,
        generation_name="output_evaluation_analyze",
        metadata={"step": "output_evaluation", "evaluation_context": "analyze"}
    )
    print(f"   ✅ Result: {result4}")
    
    time.sleep(0.5)
    
    # Generation 5: Evaluation (Graphs)
    print("\n   📝 Generation 5: Output Evaluation (Graphs)")
    result5 = invoke_llm(
        "Evaluate the quality of these graph suggestions. Answer: Good, confidence 0.90",
        as_json=True,
        trace_id=trace_id,
        generation_name="output_evaluation_evaluate_graphs",
        metadata={"step": "output_evaluation", "evaluation_context": "evaluate_graphs"}
    )
    print(f"   ✅ Result: {result5}")
    
    # Flush
    print("\n4️⃣ Flushing events to Langfuse...")
    flush_langfuse()
    print("✅ Events flushed")
    
    # Show what they'll see
    print("\n" + "=" * 80)
    print("🎯 WHAT YOU'LL SEE IN LANGFUSE DASHBOARD:")
    print("=" * 80)
    
    trace_url = f"https://cloud.langfuse.com/trace/{trace_id}"
    print(f"\n📊 Trace Name: process_single_report")
    print(f"🔗 View Trace: {trace_url}")
    print(f"📋 Trace ID: {trace_id}")
    
    print("\n📋 Structure:")
    print("""
    📊 Trace: process_single_report
    │   Metadata:
    │   - file_name: example_report.pdf
    │   - file_type: pdf
    │   - workflow_type: single_report_direct
    │
    ├─ 🤖 Generation: content_validation
    │   ├─ Prompt: "Is this a product demo trial? Answer: Yes"
    │   ├─ Response: {...}
    │   ├─ Tokens: ~50 input / ~20 output
    │   ├─ Latency: ~0.5s
    │   └─ Metadata: {step: "content_validation", node: "validation_node"}
    │
    ├─ 🤖 Generation: agricultural_analysis
    │   ├─ Prompt: "Analyze this agricultural demo data..."
    │   ├─ Response: {...}
    │   ├─ Tokens: ~150 input / ~200 output
    │   ├─ Latency: ~1.2s
    │   └─ Metadata: {step: "analysis", node: "analysis_node"}
    │
    ├─ 🤖 Generation: graph_suggestion
    │   ├─ Prompt: "Suggest charts for performance..."
    │   ├─ Response: {...}
    │   ├─ Tokens: ~100 input / ~150 output
    │   ├─ Latency: ~0.8s
    │   └─ Metadata: {step: "graph_suggestion", node: "graph_suggestion_node"}
    │
    ├─ 🤖 Generation: output_evaluation_analyze
    │   ├─ Prompt: "Evaluate the quality..."
    │   ├─ Response: {confidence: 0.85, ...}
    │   ├─ Tokens: ~80 input / ~50 output
    │   ├─ Latency: ~0.6s
    │   └─ Metadata: {step: "output_evaluation", evaluation_context: "analyze"}
    │
    └─ 🤖 Generation: output_evaluation_evaluate_graphs
        ├─ Prompt: "Evaluate the quality of graphs..."
        ├─ Response: {confidence: 0.90, ...}
        ├─ Tokens: ~80 input / ~50 output
        ├─ Latency: ~0.6s
        └─ Metadata: {step: "output_evaluation", evaluation_context: "evaluate_graphs"}
    """)
    
    print("\n" + "=" * 80)
    print("✅ Example trace created!")
    print(f"📊 View it at: {trace_url}")
    print("=" * 80)
    
    return trace_id, trace_url

if __name__ == "__main__":
    try:
        trace_id, trace_url = create_example_trace()
        print(f"\n🎯 Quick Access: {trace_url}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

