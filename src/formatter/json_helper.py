import re
import json
from typing import Optional, Any


def clean_json_from_llm_response(response: Any) -> Optional[dict]:
    """
    Cleans markdown-wrapped JSON (e.g., ```json {...} ```) from an LLM response and parses it.
    Args:
        response: Either a string or an object with `.content` containing JSON-like text.
    Returns:
        Parsed JSON as a Python dict, or None if cleaning/parsing fails.
    """
    response_text = response.content if hasattr(response, "content") else str(response)

    # Extract JSON inside markdown backticks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if not match:
        print("❌ No valid JSON found in response.")
        print(response_text)
        return None

    cleaned_json = match.group(1)

    try:
        return json.loads(cleaned_json)
    except json.JSONDecodeError:
        print("❌ Failed to decode cleaned JSON.")
        print(cleaned_json)
        return None