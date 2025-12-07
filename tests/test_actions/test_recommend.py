"""Tests for recommend action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.recommend import RecommendAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestRecommendAction:
    def test_label_property(self):
        action = RecommendAction(prompts_dir="/tmp/prompts")
        assert action.label == "ai-recommend"

    def test_execute_includes_investigation_context(self, mocker):
        """Test that investigation context is passed to Claude."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Need approach for X"
        mock_issue.fields.description = "Description here"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = (
            "INVESTIGATION RESULTS\n====================\n\nRoot cause is Y."
        )
        mock_jira.account_id = "bot-account-id"

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_result = ClaudeResult(
            content="OPTION 1: Do X\n...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = RecommendAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify investigation context was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "investigation_section" in context
        assert "Root cause is Y" in context["investigation_section"]
        assert "## Prior Investigation" in context["investigation_section"]

    def test_execute_without_investigation_context(self, mocker, caplog):
        """Test that recommend works without investigation and logs debug message."""
        import logging
        caplog.set_level(logging.DEBUG)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Need approach for X"
        mock_issue.fields.description = "Description here"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = None
        mock_jira.account_id = "bot-account-id"

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_result = ClaudeResult(
            content="OPTION 1: Do X\n...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = RecommendAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify empty investigation section was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert context["investigation_section"] == ""

        # Verify debug log was emitted
        assert any(
            "No investigation comment found" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )
