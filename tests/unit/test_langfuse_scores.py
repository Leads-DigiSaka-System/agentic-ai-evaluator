"""
Unit tests for Langfuse score modules (search_score, storage_score, workflow_score).

All score modules check LANGFUSE_CONFIGURED and call score_current_trace when enabled.
"""
import pytest
from unittest.mock import Mock, patch


class TestSearchScore:
    """Tests for monitoring.scores.search_score.log_search_scores."""

    @patch("src.monitoring.scores.search_score.LANGFUSE_CONFIGURED", False)
    def test_log_search_scores_no_op_when_not_configured(self):
        from src.monitoring.scores.search_score import log_search_scores
        log_search_scores([], 10)  # no raise, no call to score_current_trace

    @patch("src.monitoring.scores.search_score.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.scores.search_score.score_current_trace")
    def test_log_search_scores_calls_score_current_trace_when_configured(self, mock_score):
        from src.monitoring.scores.search_score import log_search_scores
        results = [{"score": 0.9, "data_quality_score": 80}]
        log_search_scores(results, 5)
        assert mock_score.call_count >= 1
        # At least search_success and possibly search_efficiency, avg_relevance_score, etc.
        names = [c[1]["name"] for c in mock_score.call_args_list]
        assert "search_success" in names


class TestStorageScore:
    """Tests for monitoring.scores.storage_score."""

    @patch("src.monitoring.scores.storage_score.LANGFUSE_CONFIGURED", False)
    def test_log_storage_rejection_scores_no_op_when_not_configured(self):
        from src.monitoring.scores.storage_score import log_storage_rejection_scores
        log_storage_rejection_scores()  # no raise

    @patch("src.monitoring.scores.storage_score.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.scores.storage_score.score_current_trace")
    def test_log_storage_rejection_scores_calls_score_when_configured(self, mock_score):
        from src.monitoring.scores.storage_score import log_storage_rejection_scores
        log_storage_rejection_scores()
        mock_score.assert_called_once()
        assert mock_score.call_args[1]["name"] == "user_approval"
        assert mock_score.call_args[1]["value"] == 0.0

    @patch("src.monitoring.scores.storage_score.LANGFUSE_CONFIGURED", False)
    def test_log_storage_scores_no_op_when_not_configured(self):
        from src.monitoring.scores.storage_score import log_storage_scores
        log_storage_scores([], {}, {"status": "success"}, "single")  # no raise

    @patch("src.monitoring.scores.storage_score.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.scores.storage_score.score_current_trace")
    def test_log_storage_scores_calls_score_when_configured(self, mock_score):
        from src.monitoring.scores.storage_score import log_storage_scores
        log_storage_scores(
            [{"analysis": {}}],
            {},
            {"status": "success"},
            "single",
        )
        assert mock_score.call_count >= 1
        names = [c[1]["name"] for c in mock_score.call_args_list]
        assert "storage_success" in names


class TestWorkflowScore:
    """Tests for monitoring.scores.workflow_score.log_workflow_scores."""

    @patch("src.monitoring.scores.workflow_score.LANGFUSE_CONFIGURED", False)
    def test_log_workflow_scores_no_op_when_not_configured(self):
        from src.monitoring.scores.workflow_score import log_workflow_scores
        log_workflow_scores({})  # no raise

    @patch("src.monitoring.scores.workflow_score.LANGFUSE_CONFIGURED", True)
    @patch("src.monitoring.scores.workflow_score.score_current_trace")
    def test_log_workflow_scores_calls_score_when_configured(self, mock_score):
        from src.monitoring.scores.workflow_score import log_workflow_scores
        log_workflow_scores({"errors": [], "output_evaluation": [{"confidence": 0.9}]})
        assert mock_score.call_count >= 1
        names = [c[1]["name"] for c in mock_score.call_args_list]
        assert "workflow_success" in names
