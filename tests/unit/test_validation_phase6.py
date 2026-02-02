"""
Unit tests for Phase 6: shared input validation and global ValidationError handler.

Tests src.shared.validation (sanitize_string, validate_message, validate_search_query,
validate_id, validate_session_id, validate_header_value) and ValidationError / handler.
"""
import pytest

from src.core.errors import ValidationError


class TestSanitizeString:
    """Tests for sanitize_string."""

    def test_returns_trimmed_string(self):
        from src.shared.validation import sanitize_string
        assert sanitize_string("  hello  ") == "hello"

    def test_enforces_min_length_raises(self):
        from src.shared.validation import sanitize_string
        with pytest.raises(ValidationError) as exc_info:
            sanitize_string("ab", min_length=3)
        assert "at least 3 characters" in exc_info.value.detail.get("error", "")

    def test_truncates_when_over_max_length(self):
        from src.shared.validation import sanitize_string
        result = sanitize_string("abcdefgh", max_length=5)
        assert result == "abcde"

    def test_wrong_type_raises(self):
        from src.shared.validation import sanitize_string
        with pytest.raises(ValidationError) as exc_info:
            sanitize_string(123)  # type: ignore
        assert "Expected string" in exc_info.value.detail.get("error", "")

    def test_removes_control_chars(self):
        from src.shared.validation import sanitize_string
        # tab(9), newline(10), cr(13), space(32) are allowed; then trim_whitespace strips
        result = sanitize_string("a\x00b\x01c\t\n\r ")
        assert result == "abc"  # control chars removed, then leading/trailing whitespace trimmed
        # other control chars (e.g. bell \x07) removed
        result2 = sanitize_string("hello\x07world")
        assert "\x07" not in result2
        assert result2 == "helloworld"

    def test_empty_after_trim_passes_with_min_length_zero(self):
        from src.shared.validation import sanitize_string
        assert sanitize_string("   ", min_length=0) == ""


class TestValidateMessage:
    """Tests for validate_message (chat)."""

    def test_valid_message_returned(self):
        from src.shared.validation import validate_message
        assert validate_message("Hello world", max_length=5000, min_length=1) == "Hello world"

    def test_empty_raises_when_min_length_one(self):
        from src.shared.validation import validate_message
        with pytest.raises(ValidationError):
            validate_message("", max_length=5000, min_length=1)
        with pytest.raises(ValidationError):
            validate_message("   ", max_length=5000, min_length=1)

    def test_truncates_over_5000(self):
        from src.shared.validation import validate_message
        long_msg = "x" * 6000
        result = validate_message(long_msg, max_length=5000, min_length=0)
        assert len(result) == 5000

    def test_default_min_length_zero(self):
        from src.shared.validation import validate_message
        assert validate_message("") == ""


class TestValidateSearchQuery:
    """Tests for validate_search_query."""

    def test_valid_query_returned(self):
        from src.shared.validation import validate_search_query
        assert validate_search_query("rice yield", max_length=500, min_length=1) == "rice yield"

    def test_empty_raises_when_min_length_one(self):
        from src.shared.validation import validate_search_query
        with pytest.raises(ValidationError):
            validate_search_query("", max_length=500, min_length=1)

    def test_truncates_over_500(self):
        from src.shared.validation import validate_search_query
        long_q = "q" * 600
        result = validate_search_query(long_q, max_length=500, min_length=0)
        assert len(result) == 500


class TestValidateId:
    """Tests for validate_id (path/body IDs)."""

    def test_valid_id_returned(self):
        from src.shared.validation import validate_id
        assert validate_id("form-123", name="form_id") == "form-123"
        assert validate_id("  cache-uuid-here  ", name="cache_id") == "cache-uuid-here"

    def test_empty_raises(self):
        from src.shared.validation import validate_id
        with pytest.raises(ValidationError) as exc_info:
            validate_id("", name="form_id")
        assert "cannot be empty" in exc_info.value.detail.get("error", "")
        with pytest.raises(ValidationError):
            validate_id("   ", name="cache_id")

    def test_too_long_raises(self):
        from src.shared.validation import validate_id, MAX_ID_LENGTH
        with pytest.raises(ValidationError) as exc_info:
            validate_id("x" * (MAX_ID_LENGTH + 1), name="form_id")
        assert "at most" in exc_info.value.detail.get("error", "") and str(MAX_ID_LENGTH) in exc_info.value.detail.get("error", "")

    def test_wrong_type_raises(self):
        from src.shared.validation import validate_id
        with pytest.raises(ValidationError):
            validate_id(12345, name="form_id")  # type: ignore

    def test_exactly_max_length_passes(self):
        from src.shared.validation import validate_id, MAX_ID_LENGTH
        s = "a" * MAX_ID_LENGTH
        assert validate_id(s, name="id") == s


class TestValidateSessionId:
    """Tests for validate_session_id (optional)."""

    def test_none_returns_none(self):
        from src.shared.validation import validate_session_id
        assert validate_session_id(None) is None

    def test_empty_string_returns_none(self):
        from src.shared.validation import validate_session_id
        assert validate_session_id("") is None
        assert validate_session_id("   ") is None

    def test_valid_returns_stripped(self):
        from src.shared.validation import validate_session_id
        assert validate_session_id("  session-abc  ") == "session-abc"

    def test_too_long_raises(self):
        from src.shared.validation import validate_session_id, MAX_SESSION_ID_LENGTH
        with pytest.raises(ValidationError):
            validate_session_id("x" * (MAX_SESSION_ID_LENGTH + 1))

    def test_wrong_type_raises(self):
        from src.shared.validation import validate_session_id
        with pytest.raises(ValidationError):
            validate_session_id(123)  # type: ignore


class TestValidateHeaderValue:
    """Tests for validate_header_value (X-Cooperative, X-User-ID)."""

    def test_valid_header_returned(self):
        from src.shared.validation import validate_header_value
        assert validate_header_value("coop-1", "X-Cooperative") == "coop-1"
        assert validate_header_value("  user-99  ", "X-User-ID") == "user-99"

    def test_empty_raises(self):
        from src.shared.validation import validate_header_value
        with pytest.raises(ValidationError) as exc_info:
            validate_header_value("", "X-Cooperative")
        assert "cannot be empty" in exc_info.value.detail.get("error", "")

    def test_too_long_raises(self):
        from src.shared.validation import validate_header_value, MAX_ID_LENGTH
        with pytest.raises(ValidationError):
            validate_header_value("x" * (MAX_ID_LENGTH + 1), "X-Cooperative")

    def test_wrong_type_raises(self):
        from src.shared.validation import validate_header_value
        with pytest.raises(ValidationError):
            validate_header_value(999, "X-User-ID")  # type: ignore


class TestValidationError:
    """Tests for ValidationError (status_code and detail structure)."""

    def test_status_code_is_400(self):
        exc = ValidationError("Invalid input")
        assert exc.status_code == 400

    def test_detail_is_dict_with_error_key(self):
        exc = ValidationError("Something wrong")
        assert isinstance(exc.detail, dict)
        assert "error" in exc.detail
        assert exc.detail["error"] == "Something wrong"

    def test_detail_includes_context_when_field_given(self):
        exc = ValidationError("Bad value", field="query", value="x")
        assert exc.detail.get("context") is not None
        assert exc.detail["context"].get("field") == "query"
        assert exc.detail["context"].get("value") == "x"


class TestValidationConstants:
    """Tests for validation module constants."""

    def test_max_id_length_defined(self):
        from src.shared.validation import MAX_ID_LENGTH, MAX_SESSION_ID_LENGTH
        assert MAX_ID_LENGTH == 200
        assert MAX_SESSION_ID_LENGTH == 200


class TestValidationExceptionHandler:
    """Tests that ValidationError handler returns 400 and structured detail (same contract as main.app)."""

    def test_handler_returns_400_and_detail(self):
        """Verify the handler contract used in main: JSONResponse(status_code=exc.status_code, content=exc.detail)."""
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from src.core.errors import ValidationError
        from fastapi.testclient import TestClient

        async def validation_exception_handler(request, exc: ValidationError):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)

        app = FastAPI()
        app.add_exception_handler(ValidationError, validation_exception_handler)

        @app.get("/raise")
        def raise_validation():
            raise ValidationError("Test validation message")

        client = TestClient(app)
        r = client.get("/raise")
        assert r.status_code == 400
        data = r.json()
        assert "error" in data
        assert data["error"] == "Test validation message"
