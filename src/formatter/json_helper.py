import re
import json
from typing import Optional, Any, Dict, List, Union
from src.utils.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def repair_json_string(json_str: str) -> str:
    """
    Attempts to repair common JSON syntax errors in LLM responses.
    
    Uses a simple, iterative approach to fix:
    - Missing commas between object properties
    - Trailing commas before closing braces/brackets
    - Invalid escape sequences (e.g., \escape -> \\escape)
    
    Args:
        json_str: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string (may still be invalid)
    """
    if not json_str:
        return json_str
    
    # Step 0: Fix invalid escape sequences
    # Replace invalid escape sequences like \escape with \\escape
    # But preserve valid escapes like \n, \t, \", etc.
    import re
    # Pattern to find invalid escape sequences (not followed by valid escape char)
    # Valid escapes: \n, \t, \r, \b, \f, \", \', \\, \/, \uXXXX
    valid_escapes = r'[nrtbf"\'/\\u]'
    # Replace invalid escapes (backslash not followed by valid escape or digit)
    json_str = re.sub(r'\\(?![nrtbf"\'/\\u0-9])', r'\\\\', json_str)
    
    # Step 1: Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    # Step 2: Fix missing commas between object properties
    # Look for pattern: "key": value (whitespace) "key"
    # This is the most common error - missing comma between properties
    lines = json_str.split('\n')
    repaired_lines = []
    
    for i, line in enumerate(lines):
        current_line = line.rstrip()
        
        # Check if line ends with a value (not comma, not closing brace) and next line starts with a key
        if i < len(lines) - 1:
            next_line = lines[i + 1].lstrip()
            
            # If current line doesn't end with comma, }, ], and next line starts with "
            # and current line contains a colon (indicating it's a key-value pair)
            if (current_line and 
                not current_line.endswith(',') and 
                not current_line.endswith('{') and
                not current_line.endswith('[') and
                not current_line.endswith('}') and
                not current_line.endswith(']') and
                ':' in current_line and
                next_line.startswith('"')):
                # Add comma at end of current line
                current_line = current_line.rstrip() + ','
        
        repaired_lines.append(current_line)
    
    json_str = '\n'.join(repaired_lines)
    
    # Step 3: Fix missing commas after closing braces/brackets when followed by a key
    # Pattern: } "key" or ] "key" -> }, "key" or ], "key"
    json_str = re.sub(r'([}\]])"', r'\1, "', json_str)
    
    # Step 4: More aggressive fix for missing commas between properties (single-line case)
    # Pattern: "key": value "key" -> "key": value, "key"
    # This handles cases where properties are on the same line
    json_str = re.sub(
        r'("(?:[^"\\]|\\.)*"\s*:\s*[^,}\]]+?)\s+("(?:[^"\\]|\\.)*"\s*:)',
        r'\1, \2',
        json_str
    )
    
    return json_str


def clean_json_from_llm_response(response: Any) -> Optional[dict]:
    """
    Cleans markdown-wrapped JSON (e.g., ```json {...} ```) from an LLM response and parses it.
    Includes JSON repair attempts for common syntax errors.
    
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
            # Try repairing and parsing again
            try:
                repaired = repair_json_string(raw)
                parsed = json.loads(repaired)
                logger.debug("Successfully repaired and parsed raw JSON")
                return parsed if isinstance(parsed, dict) else (parsed[0] if parsed and isinstance(parsed, list) else None)
            except (json.JSONDecodeError, Exception):
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
            logger.debug(f"Fenced JSON (first 200 chars): {candidate[:200]}...")
            # Log error position if available
            if hasattr(e, 'pos') and e.pos is not None:
                error_pos = e.pos
                start = max(0, error_pos - 150)
                end = min(len(candidate), error_pos + 150)
                logger.debug(f"Error at position {error_pos}: ...{candidate[start:end]}...")
                # Also log the line number if available
                if hasattr(e, 'lineno'):
                    logger.debug(f"Error at line {e.lineno}, column {getattr(e, 'colno', 'unknown')}")
            
            # Try repairing
            try:
                repaired = repair_json_string(candidate)
                parsed = json.loads(repaired)
                logger.info("✅ Successfully repaired and parsed fenced JSON")
                return parsed if isinstance(parsed, dict) else (parsed[0] if parsed and isinstance(parsed, list) else None)
            except (json.JSONDecodeError, Exception) as repair_err:
                logger.debug(f"JSON repair also failed: {str(repair_err)}")
                # Log more context around the repair error location
                if hasattr(repair_err, 'pos') and repair_err.pos is not None:
                    error_pos = repair_err.pos
                    start = max(0, error_pos - 150)
                    end = min(len(repaired), error_pos + 150)
                    logger.debug(f"Repair error context (pos {error_pos}): ...{repaired[start:end]}...")

    # 3) Fallback: find first JSON object heuristically using brace counting
    # This handles "Extra data" errors by extracting only the first complete object
    start_idx = response_text.find('{')
    if start_idx != -1:
        # Use brace counting to find the exact end of the first JSON object
        brace_count = 0
        for i in range(start_idx, len(response_text)):
            if response_text[i] == '{':
                brace_count += 1
            elif response_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found complete first object - extract only this part
                    candidate = response_text[start_idx:i+1]
                    try:
                        parsed = json.loads(candidate)
                        logger.debug("✅ Successfully parsed first JSON object using brace counting")
                        return parsed if isinstance(parsed, dict) else None
                    except json.JSONDecodeError as e:
                        # Check if it's an "Extra data" error - means we got valid JSON but there's more
                        if "Extra data" in str(e):
                            # Try to parse just the valid part before the extra data
                            error_pos = getattr(e, 'pos', None)
                            if error_pos and error_pos < len(candidate):
                                try:
                                    # Parse only up to the error position
                                    partial_candidate = candidate[:error_pos].rstrip()
                                    # Find the last complete object before error
                                    last_brace = partial_candidate.rfind('}')
                                    if last_brace != -1:
                                        partial_candidate = partial_candidate[:last_brace+1]
                                        parsed = json.loads(partial_candidate)
                                        logger.info("✅ Successfully parsed JSON object (removed extra data)")
                                        return parsed if isinstance(parsed, dict) else None
                                except:
                                    pass
                        
                        logger.debug(f"Failed to decode heuristic JSON object: {str(e)}")
                        logger.debug(f"Heuristic JSON (first 200 chars): {candidate[:200]}...")
                        
                        # Try repairing
                        try:
                            repaired = repair_json_string(candidate)
                            parsed = json.loads(repaired)
                            logger.info("✅ Successfully repaired and parsed heuristic JSON")
                            return parsed if isinstance(parsed, dict) else None
                        except (json.JSONDecodeError, Exception) as repair_err:
                            logger.debug(f"JSON repair also failed: {str(repair_err)}")
                            # Log more context around the repair error location
                            if hasattr(repair_err, 'pos') and repair_err.pos is not None:
                                error_pos = repair_err.pos
                                start = max(0, error_pos - 150)
                                end = min(len(repaired), error_pos + 150)
                                logger.debug(f"Repair error context (pos {error_pos}): ...{repaired[start:end]}...")
    
    # If all parsing attempts fail, return None
    logger.warning("No valid JSON found in LLM response after cleanup attempts")
    logger.debug(f"Response text (first 300 chars): {response_text[:300]}...")
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
                "contact": ""
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