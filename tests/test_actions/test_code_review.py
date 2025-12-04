"""Tests for code review action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.code_review import CodeReviewAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestCodeReviewAction:
    def test_label_property(self):
        action = CodeReviewAction(prompts_dir="/tmp/prompts")
        assert action.label == "ai-code-review"

    def test_extract_pr_number_from_url(self):
        action = CodeReviewAction(prompts_dir="/tmp/prompts")

        # GitHub URL format
        assert action._extract_pr_number("PR: https://github.com/owner/repo/pull/42") == 42
        assert action._extract_pr_number("See https://github.com/acme/api/pull/123 for details") == 123

    def test_extract_pr_number_from_shorthand(self):
        action = CodeReviewAction(prompts_dir="/tmp/prompts")

        assert action._extract_pr_number("PR #42") == 42
        assert action._extract_pr_number("PR: #99") == 99
        assert action._extract_pr_number("Pull Request #15") == 15

    def test_extract_pr_number_not_found(self):
        action = CodeReviewAction(prompts_dir="/tmp/prompts")

        assert action._extract_pr_number("No PR here") is None
        assert action._extract_pr_number("") is None

    def test_execute_reviews_pr(self, mocker):
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Review fix for orphaned recipes"
        mock_issue.fields.description = "PR: https://github.com/owner/repo/pull/42"

        mock_jira = MagicMock()

        mock_pr = MagicMock()
        mock_pr.number = 42

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_result = ClaudeResult(
            content="## Code Review\n\nApproved with minor suggestions.",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = CodeReviewAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify PR comment was posted
        mock_github.add_pr_comment.assert_called_once()
        pr_number, comment = mock_github.add_pr_comment.call_args[0]
        assert pr_number == 42
        assert "Code Review" in comment

        # Verify Jira label removed
        mock_jira.remove_label.assert_called_with("TEST-123", "ai-code-review")

        # Verify cleanup
        mock_github.cleanup.assert_called_once()

    def test_execute_no_pr_found(self, mocker):
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Review something"
        mock_issue.fields.description = "No PR link here"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_claude = MagicMock()

        action = CodeReviewAction(prompts_dir="/tmp/prompts")
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Should post error comment and remove label
        mock_jira.add_comment.assert_called_once()
        comment = mock_jira.add_comment.call_args[0][1]
        assert "Could not find PR" in comment

        mock_jira.remove_label.assert_called_with("TEST-123", "ai-code-review")

        # Should NOT clone or invoke Claude
        mock_github.clone_repo.assert_not_called()
        mock_claude.execute_with_template.assert_not_called()
