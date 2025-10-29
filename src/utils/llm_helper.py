from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.config import GOOGLE_API_KEY, GEMINI_MODEL
from src.formatter.json_helper import clean_json_from_llm_response
from src.utils.clean_logger import get_clean_logger

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
    logger = get_clean_logger(__name__)

    try:
        logger.llm_request(GEMINI_MODEL, "text generation" if not as_json else "json generation")
        response = llm.invoke(prompt)
        result_text = response.content if hasattr(response, "content") else str(response)

        if as_json:
            logger.llm_response(GEMINI_MODEL, "json parsed", "success")
            return clean_json_from_llm_response(result_text)

        logger.llm_response(GEMINI_MODEL, "text generated", "success")
        return result_text
    except Exception as e:
        logger.llm_error(GEMINI_MODEL, str(e))
        return None
