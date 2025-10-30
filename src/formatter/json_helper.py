import re
import json
from typing import Optional, Any, Dict, List, Union
from src.utils.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def clean_json_from_llm_response(response: Any) -> Optional[dict]:
    """
    Cleans markdown-wrapped JSON (e.g., ```json {...} ```) from an LLM response and parses it.
    Args:
        response: Either a string or an object with `.content` containing JSON-like text.
    Returns:
        Parsed JSON as a Python dict, or None if cleaning/parsing fails.
    """
    response_text = response.content if hasattr(response, "content") else str(response)

    # 1) Direct parse if response is raw JSON (object or array)
    raw = response_text.strip()
    if (raw.startswith('{') and raw.endswith('}')) or (raw.startswith('[') and raw.endswith(']')):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else (parsed[0] if parsed and isinstance(parsed, list) else None)
        except json.JSONDecodeError:
            pass

    # 2) Extract JSON inside markdown backticks (object or array)
    fenced = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", response_text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else (parsed[0] if parsed and isinstance(parsed, list) else None)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode fenced JSON: {str(e)}")
            logger.debug(f"Fenced JSON: {candidate[:200]}...")

    # 3) Fallback: find first JSON object heuristically
    obj_match = re.search(r"\{[\s\S]*\}", response_text)
    if obj_match:
        candidate = obj_match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode heuristic JSON object: {str(e)}")
            logger.debug(f"Heuristic JSON: {candidate[:200]}...")

    logger.warning("No valid JSON found in LLM response after cleanup attempts")
    logger.debug(f"Response text: {response_text[:300]}...")
    return None


def normalize_analysis_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize analysis response to ensure consistent data structure.
    
    This function fixes common inconsistencies in LLM responses:
    - Converts performance_analysis from list to dict format
    - Ensures required fields exist
    - Validates data types
    
    Args:
        response_data: Raw analysis response from LLM
        
    Returns:
        Normalized analysis response with consistent structure
    """
    try:
        logger.info("Normalizing analysis response structure")
        
        # Create a copy to avoid modifying original
        normalized = response_data.copy()
        
        # Fix performance_analysis format inconsistency
        if "performance_analysis" in normalized:
            performance_analysis = normalized["performance_analysis"]
            
            if isinstance(performance_analysis, list):
                logger.info(f"Converting performance_analysis from list ({len(performance_analysis)} items) to dict format")
                
                # Convert list to dict format
                # Take the first item as the main analysis, merge others if needed
                if performance_analysis:
                    main_analysis = performance_analysis[0].copy()
                    
                    # If there are multiple analyses, combine them
                    if len(performance_analysis) > 1:
                        logger.info(f"Merging {len(performance_analysis)} performance analyses")
                        
                        # Combine metrics from all analyses
                        combined_metrics = []
                        for i, analysis in enumerate(performance_analysis):
                            if isinstance(analysis, dict):
                                combined_metrics.append(analysis)
                        
                        # Update main analysis with combined data
                        main_analysis["combined_metrics"] = combined_metrics
                        main_analysis["total_metrics"] = len(combined_metrics)
                    
                    normalized["performance_analysis"] = main_analysis
                else:
                    # Empty list - create default structure
                    normalized["performance_analysis"] = {
                        "metric_type": "unknown",
                        "raw_data": {},
                        "calculated_metrics": {},
                        "statistical_assessment": {},
                        "trend_analysis": {}
                    }
            
            elif isinstance(performance_analysis, dict):
                logger.info("performance_analysis already in dict format")
                # Already correct format, no changes needed
            else:
                logger.warning(f"Unexpected performance_analysis type: {type(performance_analysis)}")
                # Create default structure
                normalized["performance_analysis"] = {
                    "metric_type": "unknown",
                    "raw_data": {},
                    "calculated_metrics": {},
                    "statistical_assessment": {},
                    "trend_analysis": {}
                }
        
        # Ensure basic_info exists
        if "basic_info" not in normalized:
            logger.info("Adding missing basic_info structure")
            normalized["basic_info"] = {
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
            }
        
        # Ensure recommendations is always a list
        if "recommendations" not in normalized:
            normalized["recommendations"] = []
        elif not isinstance(normalized["recommendations"], list):
            logger.warning("Converting recommendations to list format")
            normalized["recommendations"] = [normalized["recommendations"]]
        
        # Ensure risk_factors is always a list
        if "risk_factors" not in normalized:
            normalized["risk_factors"] = []
        elif not isinstance(normalized["risk_factors"], list):
            logger.warning("Converting risk_factors to list format")
            normalized["risk_factors"] = [normalized["risk_factors"]]
        
        # Ensure opportunities is always a list
        if "opportunities" not in normalized:
            normalized["opportunities"] = []
        elif not isinstance(normalized["opportunities"], list):
            logger.warning("Converting opportunities to list format")
            normalized["opportunities"] = [normalized["opportunities"]]
        
        logger.info("Analysis response normalization completed")
        return normalized
        
    except Exception as e:
        logger.error(f"Failed to normalize analysis response: {str(e)}")
        # Return original data if normalization fails
        return response_data


def validate_and_clean_agent_response(agent_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean the complete agent response.
    
    This function ensures the entire agent response has consistent structure
    and all analysis data is properly normalized.
    
    Args:
        agent_response: Complete agent response from MultiReportHandler
        
    Returns:
        Cleaned and validated agent response
    """
    try:
        logger.info("Validating and cleaning agent response")
        
        # Create a copy to avoid modifying original
        cleaned_response = agent_response.copy()
        
        # Process each report
        if "reports" in cleaned_response and isinstance(cleaned_response["reports"], list):
            logger.info(f"Processing {len(cleaned_response['reports'])} reports")
            
            for i, report in enumerate(cleaned_response["reports"]):
                if isinstance(report, dict) and "analysis" in report:
                    logger.info(f"Normalizing analysis for report {i+1}")
                    
                    # Normalize the analysis data
                    report["analysis"] = normalize_analysis_response(report["analysis"])
                    
                    # Ensure storage_status is set
                    if "storage_status" not in report:
                        report["storage_status"] = "ready_for_approval"
                    
                    # Ensure storage_message is set
                    if "storage_message" not in report:
                        report["storage_message"] = "Analysis completed. Ready for storage approval."
        
        logger.info("Agent response validation and cleaning completed")
        return cleaned_response
        
    except Exception as e:
        logger.error(f"Failed to validate and clean agent response: {str(e)}")
        # Return original response if cleaning fails
        return agent_response