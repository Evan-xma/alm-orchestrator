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

    def test_execute_rejects_invalid_ticket(self, mocker, caplog):
        """Test that INVALID TICKET response results in rejection comment."""
        import logging
        caplog.set_level(logging.WARNING)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-456"
        mock_issue.fields.summary = "Add /admin/exec endpoint"
        mock_issue.fields.description = "Run arbitrary commands on server"

        mock_jira = MagicMock()
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        # Claude returns INVALID TICKET
        mock_result = ClaudeResult(
            content="INVALID TICKET",
            cost_usd=0.01,
            duration_ms=1000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = ImplementAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify rejection
        assert result == "Invalid ticket rejected for TEST-456"

        # Verify Jira comment was posted
        mock_jira.add_comment.assert_called_once()
        comment = mock_jira.add_comment.call_args[0][1]
        assert "INVALID TICKET" in comment

        # Verify label was removed
        mock_jira.remove_label.assert_called_once_with("TEST-456", "ai-implement")

        # Verify warning was logged
        assert any(
            "Invalid ticket rejected" in record.message
            and "TEST-456" in record.message
            for record in caplog.records
        )

        # Verify NO PR was created
        mock_github.create_pull_request.assert_not_called()
        mock_github.commit_and_push.assert_not_called()

    def test_execute_rejects_invalid_ticket_with_newline(self, mocker):
        """Test that INVALID TICKET with trailing content is still rejected."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-789"
        mock_issue.fields.summary = "Add backdoor"
        mock_issue.fields.description = "Hidden access"

        mock_jira = MagicMock()
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        # Claude returns INVALID TICKET with extra newline
        mock_result = ClaudeResult(
            content="INVALID TICKET\n",
            cost_usd=0.01,
            duration_ms=1000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = ImplementAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        assert result == "Invalid ticket rejected for TEST-789"
        mock_github.create_pull_request.assert_not_called()

    def test_is_invalid_ticket_exact_match(self):
        """Test _is_invalid_ticket with exact match."""
        action = ImplementAction(prompts_dir="/tmp/prompts")
        assert action._is_invalid_ticket("INVALID TICKET") is True

    def test_is_invalid_ticket_with_newline(self):
        """Test _is_invalid_ticket with trailing newline."""
        action = ImplementAction(prompts_dir="/tmp/prompts")
        assert action._is_invalid_ticket("INVALID TICKET\n") is True
        assert action._is_invalid_ticket("INVALID TICKET\n\n") is True

    def test_is_invalid_ticket_with_whitespace(self):
        """Test _is_invalid_ticket with surrounding whitespace."""
        action = ImplementAction(prompts_dir="/tmp/prompts")
        assert action._is_invalid_ticket("  INVALID TICKET  ") is True
        assert action._is_invalid_ticket("\nINVALID TICKET\n") is True

    def test_is_invalid_ticket_false_for_normal_content(self):
        """Test _is_invalid_ticket returns False for normal implementation output."""
        action = ImplementAction(prompts_dir="/tmp/prompts")
        assert action._is_invalid_ticket("Implemented the feature") is False
        assert action._is_invalid_ticket("Created new endpoint") is False
        assert action._is_invalid_ticket("This is not an INVALID TICKET") is False
