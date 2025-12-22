"""Tests for impact action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.impact import ImpactAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestImpactAction:
    def test_label_property(self):
        action = ImpactAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        assert action.label == "ai-impact"

    def test_allowed_issue_types(self):
        action = ImpactAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        assert action.allowed_issue_types == ["Bug", "Story"]

    def test_execute_rejects_invalid_issue_type(self):
        """Execute returns early for non-Bug/Story issue types."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.issuetype.name = "Task"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_claude = MagicMock()

        action = ImpactAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        mock_github.clone_repo.assert_not_called()
        mock_claude.execute_with_template.assert_not_called()
        mock_jira.add_comment.assert_called_once()
        assert "INVALID ISSUE TYPE" in mock_jira.add_comment.call_args[0][1]
        assert "Rejected" in result

    def test_execute_flow(self):
        """Test successful execution for valid Bug type."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Performance degradation"
        mock_issue.fields.description = "API response times increased"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_result = ClaudeResult(
            content="Impact: High - affects all API consumers",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = ImpactAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        mock_github.clone_repo.assert_called_once()
        mock_claude.execute_with_template.assert_called_once()
        mock_jira.add_comment.assert_called_once()
        assert "IMPACT ANALYSIS" in mock_jira.add_comment.call_args[0][1]
        mock_jira.remove_label.assert_called_once_with("TEST-123", "ai-impact")
        mock_github.cleanup.assert_called_once()
