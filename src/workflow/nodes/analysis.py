# file: src/workflow/nodes/analysis.py (FIXED)
from src.prompt.analysis_template import analysis_prompt_template_structured
from src.utils.llm_helper import invoke_llm
from typing import List
import traceback

def analyze_demo_trial(markdown_data: str):
    """
    Universal analyzer that adapts to ANY agricultural demo form
    
    Automatically detects:
    - Product type (herbicide, foliar, fungicide, etc.)
    - Metrics used (ratings, percentages, counts, measurements)
    - Assessment intervals (3/7/14 DAA, 10/18 DAA, etc.)
    
    Args:
        markdown_data: Extracted markdown content
    
    Returns:
        Adaptive analysis results dict
    """
    try:
        print("🔍 Starting universal adaptive analysis...")
        
        # Truncate if too long
        if len(markdown_data) > 4000:
            markdown_data = markdown_data[:4000] + "\n... (truncated)"
            print("📏 Content truncated to 4000 characters")
        
        # Use single universal template
        template = analysis_prompt_template_structured()
        prompt = template.format(markdown_data=markdown_data)
        
        print("📤 Sending to Universal Agricultural Demo Analyst...")
        result = invoke_llm(prompt, as_json=True)
        
        if not result:
            error_msg = "No response from LLM"
            print(f"❌ {error_msg}")
            return create_universal_error_response(error_msg)
        
        print(f"✅ LLM response received, type: {type(result)}")
        
        # Validate response
        if isinstance(result, dict):
            if result.get("status") == "error":
                print(f"⚠️ Analysis returned error: {result.get('error_message', 'Unknown error')}")
            else:
                # Show what was detected
                product_category = result.get("product_category", "unknown")
                metrics = result.get("metrics_detected", [])
                print(f"🎯 Analysis completed successfully")
                print(f"   Product Category: {product_category}")
                print(f"   Metrics Detected: {', '.join(metrics)}")
                
                # Generate summary if missing
                if not result.get("executive_summary"):
                    result["executive_summary"] = generate_adaptive_summary(result)
        else:
            print(f"⚠️ Unexpected response type: {type(result)}")
            result = create_universal_error_response(f"Unexpected response type: {type(result)}")
        
        return result
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        return create_universal_error_response(error_msg)


def generate_adaptive_summary(analysis_data):
    """Generate fallback summary that adapts to the data structure"""
    try:
        basic_info = analysis_data.get("basic_info", {})
        performance = analysis_data.get("performance_analysis", {})
        calculated = performance.get("calculated_metrics", {})
        
        product = basic_info.get("product", "Product")
        cooperator = basic_info.get("cooperator", "Unknown")
        location = basic_info.get("location", "Unknown location")
        improvement = calculated.get("improvement_percent", 0)
        product_category = analysis_data.get("product_category", "agricultural product")
        
        return f"{product} ({product_category}) trial with {cooperator} in {location} showed {improvement}% improvement over control."
    except:
        return "Agricultural demo analysis completed. See detailed results for more information."


def create_universal_error_response(message):
    """Create standardized error response for universal template"""
    return {
        "status": "error",
        "product_category": "unknown",
        "metrics_detected": [],
        "measurement_intervals": [],
        
        "data_quality": {
            "completeness_score": 0,
            "critical_data_present": False,
            "sample_size_adequate": False,
            "reliability_notes": message,
            "missing_fields": ["all"]
        },
        
        "basic_info": {
            "cooperator": "",
            "product": "",
            "location": "",
            "application_date": "",
            "planting_date": "",
            "crop": "",
            "plot_size": "",
            "contact": "",
            "participants": 0,
            "total_sales": 0
        },
        
        "treatment_comparison": {
            "control": {
                "description": "",
                "product": "",
                "rate": "",
                "timing": "",
                "method": "",
                "applications": ""
            },
            "leads_agri": {
                "product": "",
                "rate": "",
                "timing": "",
                "method": "",
                "applications": ""
            },
            "protocol_assessment": ""
        },
        
        "performance_analysis": {
            "metric_type": "unknown",
            "rating_scale_info": "",
            "raw_data": {
                "control": {},
                "leads_agri": {}
            },
            "calculated_metrics": {
                "control_average": 0,
                "leads_average": 0,
                "improvement_value": 0,
                "improvement_percent": 0,
                "improvement_interpretation": ""
            },
            "statistical_assessment": {
                "improvement_significance": "unknown",
                "performance_consistency": "unknown",
                "confidence_level": "low",
                "notes": message
            },
            "trend_analysis": {
                "control_trend": "unknown",
                "leads_trend": "unknown",
                "key_observation": "",
                "speed_of_action": "unknown"
            }
        },
        
        "yield_analysis": {
            "control_yield": "",
            "leads_yield": "",
            "yield_improvement": 0,
            "yield_status": "not_available"
        },
        
        "cooperator_feedback": {
            "raw_feedback": "",
            "sentiment": "unknown",
            "key_highlights": [],
            "visible_results_timeline": "",
            "concerns": []
        },
        
        "commercial_metrics": {
            "demo_date": "",
            "participants": 0,
            "total_sales": 0,
            "sales_per_participant": 0,
            "demo_conducted": False,
            "market_reception": ""
        },
        
        "risk_factors": [],
        "opportunities": [],
        "recommendations": [],
        "executive_summary": "",
        "error_message": message
    }



# Alias for backward compatibility
analyze_agricultural_demo = analyze_demo_trial