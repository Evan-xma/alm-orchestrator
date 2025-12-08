"""Tests for implement action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.implement import ImplementAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestImplementAction:
    def test_execute_includes_recommendation_context(self, mocker):
        """Test that recommendation context is passed to Claude."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Add user dashboard"
        mock_issue.fields.description = "Create a dashboard for users"

        mock_jira = MagicMock()
        mock_jira.get_recommendation_comment.return_value = (
            "RECOMMENDATIONS\n===============\n\nOption 1: Use React components."
        )

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Implemented dashboard",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = ImplementAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify recommendation context was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "prior_analysis_section" in context
        assert "Option 1: Use React components" in context["prior_analysis_section"]
        assert "## Recommended Approach" in context["prior_analysis_section"]

    def test_execute_without_recommendation(self, mocker, caplog):
        """Test that implement works without recommendation context."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Add user dashboard"
        mock_issue.fields.description = "Create a dashboard for users"

        mock_jira = MagicMock()
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Implemented dashboard",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = ImplementAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify empty prior analysis section was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert context["prior_analysis_section"] == ""

        # Verify info log was emitted
        assert any(
            "No recommendation comment found" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )
