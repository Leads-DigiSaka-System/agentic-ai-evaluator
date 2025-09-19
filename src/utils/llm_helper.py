from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.config import GOOGLE_API_KEY, GEMINI_MODEL
from src.formatter.json_helper import clean_json_from_llm_response

# Shared Gemini instance (singleton)
llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,

)

def invoke_llm(prompt: str, as_json: bool = False):
    """
    Send a prompt to Gemini and return the response.

    Args:
        prompt (str): Prompt string to send
        as_json (bool): If True, tries to clean and return parsed JSON

    Returns:
        str or dict: Raw string response or parsed dict
    """

    try:
        response = llm.invoke(prompt)
        result_text = response.content if hasattr(response, "content") else str(response)

        if as_json:
            return clean_json_from_llm_response(result_text)

        return result_text
    except Exception as e:
        print("❌ LLM call failed:", e)
        return None
