"""
Analysis tools for chat agent - comparison, summarization, and trend analysis
"""
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from src.database.analysis_search import analysis_searcher
from src.database.list_reports import report_lister
from src.utils.clean_logger import get_clean_logger
from src.utils.llm_helper import ainvoke_llm
from src.utils.config import GEMINI_MODEL
import json
import asyncio

logger = get_clean_logger(__name__)


@tool
def compare_products_tool(
    product_names: str,
    cooperative: str = None
) -> str:
    """
    Compare multiple products based on their performance data.
    
    Use this tool when the user asks:
    - "Compare Product A and Product B"
    - "Which product performs better?"
    - "Show me differences between products"
    
    Args:
        product_names: Comma-separated list of product names to compare (e.g., "Product A, Product B")
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with comparison data including improvement percentages, locations, and recommendations
    """
    try:
        if not product_names or not product_names.strip():
            return '{"error": "Product names are required", "comparison": {}}'
        
        if not cooperative:
            return '{"error": "Cooperative ID is required", "comparison": {}}'
        
        # Parse product names
        products = [p.strip() for p in product_names.split(",") if p.strip()]
        if len(products) < 2:
            return '{"error": "At least 2 products are required for comparison", "comparison": {}}'
        
        # Search for each product
        all_results = {}
        
        for product in products:
            try:
                # Call async search
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            analysis_searcher.search(f"product: {product}", top_k=10, cooperative=cooperative)
                        )
                        results = future.result(timeout=30)
                else:
                    results = loop.run_until_complete(
                        analysis_searcher.search(f"product: {product}", top_k=10, cooperative=cooperative)
                    )
                
                all_results[product] = results if results else []
            except Exception as e:
                logger.warning(f"Error searching for product {product}: {str(e)}")
                all_results[product] = []
        
        # Calculate comparison metrics
        comparison_data = {}
        for product, results in all_results.items():
            if not results:
                comparison_data[product] = {
                    "found": False,
                    "message": f"No data found for {product}"
                }
                continue
            
            # Calculate averages
            improvements = [r.get("improvement_percent", 0.0) for r in results if isinstance(r.get("improvement_percent"), (int, float))]
            locations = list(set([r.get("location", "") for r in results if r.get("location")]))
            crops = list(set([r.get("crop", "") for r in results if r.get("crop")]))
            
            avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0
            max_improvement = max(improvements) if improvements else 0.0
            min_improvement = min(improvements) if improvements else 0.0
            
            # Extract existing executive summaries and recommendations from full_analysis
            executive_summaries = []
            recommendations = []
            risk_factors = []
            opportunities = []
            
            for result in results:
                # Get executive summary if available
                exec_summary = result.get("executive_summary", "")
                if exec_summary:
                    executive_summaries.append(exec_summary[:150])  # Limit length
                
                # Extract from full_analysis
                full_analysis = result.get("full_analysis", {})
                if isinstance(full_analysis, dict):
                    # Get recommendations
                    recs = full_analysis.get("recommendations", [])
                    for rec in recs[:1]:  # Limit to 1 per report
                        if isinstance(rec, dict):
                            recommendations.append(rec.get("recommendation", ""))
                        elif isinstance(rec, str):
                            recommendations.append(rec)
                    
                    # Get risk factors
                    risks = full_analysis.get("risk_factors", [])
                    for risk in risks[:1]:
                        if isinstance(risk, dict):
                            risk_factors.append(risk.get("risk", ""))
                    
                    # Get opportunities
                    opps = full_analysis.get("opportunities", [])
                    for opp in opps[:1]:
                        if isinstance(opp, dict):
                            opportunities.append(opp.get("opportunity", ""))
            
            comparison_data[product] = {
                "found": True,
                "total_demos": len(results),
                "average_improvement": round(avg_improvement, 2),
                "max_improvement": round(max_improvement, 2),
                "min_improvement": round(min_improvement, 2),
                "locations": locations[:5],  # Limit to 5
                "crops": crops[:5],
                "executive_summaries": executive_summaries[:3],  # Include existing summaries
                "top_recommendations": list(set(recommendations))[:3],  # Unique recommendations
                "risk_factors": list(set(risk_factors))[:2],
                "opportunities": list(set(opportunities))[:2]
            }
        
        # Determine best performing product
        best_product = None
        best_avg = -1
        for product, data in comparison_data.items():
            if data.get("found") and data.get("average_improvement", 0) > best_avg:
                best_avg = data.get("average_improvement", 0)
                best_product = product
        
        return json.dumps({
            "products_compared": products,
            "comparison": comparison_data,
            "best_performing": best_product if best_product else None,
            "best_average_improvement": round(best_avg, 2) if best_product else None
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Compare products tool error: {str(e)}", exc_info=True)
        return f'{{"error": "Failed to compare products: {str(e)}", "comparison": {{}}}}'


@tool
def generate_summary_tool(
    query: str,
    top_k: int = 5,
    cooperative: str = None
) -> str:
    """
    Generate a summary and insights from search results using EXISTING executive summaries and recommendations.
    
    Use this tool when the user asks:
    - "Summarize the results"
    - "What are the key insights?"
    - "Give me a summary of rice demos"
    
    This tool aggregates existing executive summaries and recommendations from reports instead of generating new ones.
    
    Args:
        query: Search query to find data to summarize
        top_k: Number of results to include in summary (default: 5)
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with aggregated summary, key insights, and recommendations from existing reports
    """
    try:
        if not query or not query.strip():
            return '{"error": "Query is required", "summary": ""}'
        
        if not cooperative:
            return '{"error": "Cooperative ID is required", "summary": ""}'
        
        if top_k < 1:
            top_k = 5
        if top_k > 10:
            top_k = 10  # Limit for summary generation
        
        # Search for data
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    analysis_searcher.search(query, top_k=top_k, cooperative=cooperative)
                )
                results = future.result(timeout=30)
        else:
            results = loop.run_until_complete(
                analysis_searcher.search(query, top_k=top_k, cooperative=cooperative)
            )
        
        if not results:
            return json.dumps({
                "query": query,
                "summary": f"No data found for query: {query}",
                "insights": [],
                "recommendations": []
            })
        
        # Extract existing data from reports
        executive_summaries = []
        all_recommendations = []
        all_risk_factors = []
        all_opportunities = []
        insights = []
        
        for result in results:
            # Get executive summary (already exists in report)
            exec_summary = result.get("executive_summary", "")
            if exec_summary:
                executive_summaries.append({
                    "product": result.get("product", "N/A"),
                    "location": result.get("location", "N/A"),
                    "summary": exec_summary[:200]  # Limit length
                })
            
            # Extract from full_analysis if available
            full_analysis = result.get("full_analysis", {})
            if isinstance(full_analysis, dict):
                # Get recommendations
                recommendations = full_analysis.get("recommendations", [])
                if recommendations:
                    for rec in recommendations[:2]:  # Limit to 2 per report
                        if isinstance(rec, dict):
                            all_recommendations.append(rec.get("recommendation", ""))
                        elif isinstance(rec, str):
                            all_recommendations.append(rec)
                
                # Get risk factors
                risk_factors = full_analysis.get("risk_factors", [])
                if risk_factors:
                    for risk in risk_factors[:2]:
                        if isinstance(risk, dict):
                            all_risk_factors.append(risk.get("risk", ""))
                
                # Get opportunities
                opportunities = full_analysis.get("opportunities", [])
                if opportunities:
                    for opp in opportunities[:2]:
                        if isinstance(opp, dict):
                            all_opportunities.append(opp.get("opportunity", ""))
            
            # Collect performance insights
            improvement = result.get("improvement_percent", 0.0)
            if improvement > 0:
                insights.append(
                    f"{result.get('product', 'Product')} in {result.get('location', 'Location')}: "
                    f"{improvement:.1f}% improvement"
                )
        
        # Aggregate summaries
        if executive_summaries:
            # Use LLM to synthesize multiple executive summaries
            summaries_text = "\n\n".join([
                f"Product: {s['product']}, Location: {s['location']}\n{s['summary']}"
                for s in executive_summaries
            ])
            
            prompt = f"""You are an agricultural data analyst. Synthesize the following executive summaries from multiple demo reports into:
1. A concise overall summary (2-3 sentences)
2. Key insights (3-5 bullet points)
3. Top recommendations (3-5 actionable items)

Executive Summaries:
{summaries_text}

Provide your response in JSON format:
{{
    "summary": "<concise overall summary>",
    "insights": ["<insight 1>", "<insight 2>", ...],
    "recommendations": ["<recommendation 1>", "<recommendation 2>", ...]
}}
"""
            
            try:
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            ainvoke_llm(prompt, as_json=True, trace_name="synthesize_summaries", model=GEMINI_MODEL)
                        )
                        llm_response = future.result(timeout=60)
                else:
                    llm_response = loop.run_until_complete(
                        ainvoke_llm(prompt, as_json=True, trace_name="synthesize_summaries", model=GEMINI_MODEL)
                    )
                
                if isinstance(llm_response, dict):
                    summary_data = llm_response
                else:
                    summary_data = json.loads(str(llm_response)) if isinstance(llm_response, str) else {}
                
                # Combine LLM synthesis with extracted recommendations
                final_recommendations = summary_data.get("recommendations", [])
                if all_recommendations:
                    # Add unique recommendations from reports
                    for rec in all_recommendations[:3]:
                        if rec and rec not in final_recommendations:
                            final_recommendations.append(rec)
                
                return json.dumps({
                    "query": query,
                    "data_points_analyzed": len(results),
                    "summary": summary_data.get("summary", "Summary synthesis failed"),
                    "insights": summary_data.get("insights", insights[:5]),
                    "recommendations": final_recommendations[:5],
                    "risk_factors": list(set(all_risk_factors))[:3],
                    "opportunities": list(set(all_opportunities))[:3]
                }, indent=2)
                
            except Exception as llm_error:
                logger.warning(f"LLM synthesis failed, using aggregated summaries: {str(llm_error)}")
                # Fallback: aggregate existing summaries
                aggregated_summary = " ".join([s["summary"] for s in executive_summaries[:3]])
                
                return json.dumps({
                    "query": query,
                    "data_points_analyzed": len(results),
                    "summary": aggregated_summary[:500] + "..." if len(aggregated_summary) > 500 else aggregated_summary,
                    "insights": insights[:5],
                    "recommendations": list(set(all_recommendations))[:5] if all_recommendations else ["Review individual reports for detailed recommendations"],
                    "risk_factors": list(set(all_risk_factors))[:3],
                    "opportunities": list(set(all_opportunities))[:3]
                }, indent=2)
        else:
            # No executive summaries available, use simple aggregation
            improvements = [r.get("improvement_percent", 0.0) for r in results if isinstance(r.get("improvement_percent"), (int, float))]
            avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0
            
            return json.dumps({
                "query": query,
                "data_points_analyzed": len(results),
                "summary": f"Found {len(results)} results with average improvement of {avg_improvement:.2f}%",
                "insights": insights[:5] if insights else [f"Average improvement: {avg_improvement:.2f}%"],
                "recommendations": list(set(all_recommendations))[:5] if all_recommendations else ["Review individual results for detailed analysis"],
                "risk_factors": list(set(all_risk_factors))[:3],
                "opportunities": list(set(all_opportunities))[:3]
            }, indent=2)
        
    except Exception as e:
        logger.error(f"Generate summary tool error: {str(e)}", exc_info=True)
        return f'{{"error": "Failed to generate summary: {str(e)}", "summary": ""}}'


@tool
def get_trends_tool(
    product_name: str = None,
    location: str = None,
    crop: str = None,
    cooperative: str = None
) -> str:
    """
    Analyze trends over time for products, locations, or crops.
    
    Use this tool when the user asks:
    - "Show me trends for Product X"
    - "What are the trends in Laguna?"
    - "How has rice performance changed?"
    
    Args:
        product_name: Optional product name to filter by
        location: Optional location to filter by
        crop: Optional crop type to filter by
        cooperative: Cooperative ID for data isolation (required, passed automatically)
    
    Returns:
        JSON string with trend analysis including performance over time
    """
    try:
        if not cooperative:
            return '{"error": "Cooperative ID is required", "trends": {}}'
        
        # Build search query
        query_parts = []
        if product_name:
            query_parts.append(f"product: {product_name}")
        if location:
            query_parts.append(f"location: {location}")
        if crop:
            query_parts.append(f"crop: {crop}")
        
        query = " ".join(query_parts) if query_parts else "all"
        
        # Get all reports (for trend analysis, we need more data)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    report_lister.list_all_reports(cooperative=cooperative)
                )
                result = future.result(timeout=30)
        else:
            result = loop.run_until_complete(
                report_lister.list_all_reports(cooperative=cooperative)
            )
        
        if not result or "reports" not in result:
            return '{"error": "No data found for trend analysis", "trends": {}}'
        
        reports = result.get("reports", [])
        
        # Filter by criteria if provided
        if product_name:
            reports = [r for r in reports if product_name.lower() in r.get("product", "").lower()]
        if location:
            reports = [r for r in reports if location.lower() in r.get("location", "").lower()]
        if crop:
            reports = [r for r in reports if crop.lower() in r.get("crop", "").lower()]
        
        if not reports:
            return json.dumps({
                "query": query,
                "trends": {},
                "message": "No data found matching criteria"
            })
        
        # Group by date (if available) or analyze overall
        improvements = [r.get("improvement_percent", 0.0) for r in reports if isinstance(r.get("improvement_percent"), (int, float))]
        
        if not improvements:
            return json.dumps({
                "query": query,
                "trends": {},
                "message": "No improvement data available"
            })
        
        # Calculate trend metrics
        avg_improvement = sum(improvements) / len(improvements)
        max_improvement = max(improvements)
        min_improvement = min(improvements)
        
        # Simple trend: compare first half vs second half (if enough data)
        trend_direction = "stable"
        if len(improvements) >= 4:
            mid = len(improvements) // 2
            first_half_avg = sum(improvements[:mid]) / mid
            second_half_avg = sum(improvements[mid:]) / (len(improvements) - mid)
            
            if second_half_avg > first_half_avg * 1.1:
                trend_direction = "improving"
            elif second_half_avg < first_half_avg * 0.9:
                trend_direction = "declining"
        
        return json.dumps({
            "query": query,
            "total_data_points": len(reports),
            "trends": {
                "average_improvement": round(avg_improvement, 2),
                "max_improvement": round(max_improvement, 2),
                "min_improvement": round(min_improvement, 2),
                "trend_direction": trend_direction,
                "data_points": len(improvements)
            },
            "filter_applied": {
                "product": product_name or "all",
                "location": location or "all",
                "crop": crop or "all"
            }
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Get trends tool error: {str(e)}", exc_info=True)
        return f'{{"error": "Failed to analyze trends: {str(e)}", "trends": {{}}}}'


# Helper function to get all analysis tools
def get_analysis_tools(cooperative: str) -> List:
    """
    Get all analysis tools with cooperative context.
    
    Args:
        cooperative: Cooperative ID for data isolation
    
    Returns:
        List of LangChain tools
    """
    return [
        compare_products_tool,
        generate_summary_tool,
        get_trends_tool
    ]

