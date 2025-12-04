"""Tests for investigate action handler."""

import pytest
from unittest.mock import MagicMock, mock_open, patch
from alm_orchestrator.actions.investigate import InvestigateAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestInvestigateAction:
    def test_label_property(self):
        action = InvestigateAction(prompts_dir="/tmp/prompts")
        assert action.label == "ai-investigate"

    def test_execute_flow(self, mocker):
        # Setup mocks
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Bug in recipe deletion"
        mock_issue.fields.description = "When deleting an author, recipes are orphaned"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_result = ClaudeResult(
            content="Root cause: Missing cascade delete",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = InvestigateAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify clone happened
        mock_github.clone_repo.assert_called_once()

        # Verify Claude was invoked with correct template
        mock_claude.execute_with_template.assert_called_once()
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        assert call_kwargs["work_dir"] == "/tmp/work-dir"
        assert "investigate.md" in call_kwargs["template_path"]
        assert call_kwargs["context"]["issue_key"] == "TEST-123"

        # Verify comment was posted to Jira
        mock_jira.add_comment.assert_called_once()
        comment_args = mock_jira.add_comment.call_args[0]
        assert comment_args[0] == "TEST-123"
        assert "Root cause" in comment_args[1]

        # Verify label was removed
        mock_jira.remove_label.assert_called_once_with("TEST-123", "ai-investigate")

        # Verify cleanup
        mock_github.cleanup.assert_called_once_with("/tmp/work-dir")

        # Verify return message
        assert "TEST-123" in result

    def test_cleanup_on_error(self, mocker):
        """Verify cleanup happens even when Claude fails."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Bug"
        mock_issue.fields.description = "Description"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_claude = MagicMock()
        mock_claude.execute_with_template.side_effect = Exception("Claude failed")

        action = InvestigateAction(prompts_dir="/tmp/prompts")

        with pytest.raises(Exception, match="Claude failed"):
            action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Cleanup should still happen
        mock_github.cleanup.assert_called_once_with("/tmp/work-dir")
