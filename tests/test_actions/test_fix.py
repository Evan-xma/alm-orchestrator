"""Tests for fix action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.fix import FixAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestFixAction:
    def test_label_property(self):
        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        assert action.label == "ai-fix"

    def test_allowed_issue_types(self):
        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        assert action.allowed_issue_types == ["Bug"]

    def test_execute_rejects_invalid_issue_type(self):
        """Execute returns early for non-Bug issue types."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.issuetype.name = "Story"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_claude = MagicMock()

        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Should not clone repo or invoke Claude
        mock_github.clone_repo.assert_not_called()
        mock_claude.execute_with_template.assert_not_called()

        # Should post rejection comment and remove label
        mock_jira.add_comment.assert_called_once()
        assert "INVALID ISSUE TYPE" in mock_jira.add_comment.call_args[0][1]
        mock_jira.remove_label.assert_called_once_with("TEST-123", "ai-fix")

        # Should return rejection message
        assert "Rejected" in result
        assert "TEST-123" in result

    def test_execute_creates_pr(self, mocker):
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix orphaned recipes"
        mock_issue.fields.description = "Delete cascades incorrectly"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()

        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.html_url = "https://github.com/owner/repo/pull/42"

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the cascade delete",
            cost_usd=0.10,
            duration_ms=10000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify Claude was invoked with correct action
        mock_claude.execute_with_template.assert_called_once()
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        assert call_kwargs["action"] == "fix"

        # Verify branch was created
        mock_github.create_branch.assert_called_once()
        branch_name = mock_github.create_branch.call_args[0][1]
        assert "test-123" in branch_name.lower()

        # Verify changes were committed and pushed
        mock_github.commit_and_push.assert_called_once()

        # Verify PR was created
        mock_github.create_pull_request.assert_called_once()
        pr_kwargs = mock_github.create_pull_request.call_args[1]
        assert "TEST-123" in pr_kwargs["title"] or "TEST-123" in pr_kwargs["body"]

        # Verify Jira comment with PR link
        mock_jira.add_comment.assert_called()
        comment_body = mock_jira.add_comment.call_args[0][1]
        assert "pull/42" in comment_body or mock_pr.html_url in comment_body

        # Verify label removed
        mock_jira.remove_label.assert_called_with("TEST-123", "ai-fix")

        # Verify cleanup
        mock_github.cleanup.assert_called_once_with("/tmp/work-dir")

    def test_cleanup_on_error(self, mocker):
        """Verify cleanup happens even when Claude fails."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Bug"
        mock_issue.fields.description = "Description"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_claude = MagicMock()
        mock_claude.execute_with_template.side_effect = Exception("Claude failed")

        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())

        with pytest.raises(Exception, match="Claude failed"):
            action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Cleanup should still happen
        mock_github.cleanup.assert_called_once_with("/tmp/work-dir")

    def test_execute_includes_both_contexts(self, mocker):
        """Test that both investigation and recommendation context are passed to Claude."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = (
            "INVESTIGATION RESULTS\n====================\n\nRoot cause is Y."
        )
        mock_jira.get_recommendation_comment.return_value = (
            "RECOMMENDATIONS\n===============\n\nOption 1: Do X."
        )

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify both contexts were passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "prior_analysis_section" in context
        assert "Root cause is Y" in context["prior_analysis_section"]
        assert "Option 1: Do X" in context["prior_analysis_section"]
        assert "## Prior Investigation" in context["prior_analysis_section"]
        assert "## Recommendations" in context["prior_analysis_section"]

    def test_execute_with_only_investigation(self, mocker, caplog):
        """Test that fix works with only investigation context."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = (
            "INVESTIGATION RESULTS\n====================\n\nRoot cause is Y."
        )
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify investigation context was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "Root cause is Y" in context["prior_analysis_section"]
        assert "## Recommendations" not in context["prior_analysis_section"]

        # Verify info log was emitted for missing recommendation
        assert any(
            "No recommendation comment found" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )

    def test_execute_with_only_recommendation(self, mocker, caplog):
        """Test that fix works with only recommendation context."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = None
        mock_jira.get_recommendation_comment.return_value = (
            "RECOMMENDATIONS\n===============\n\nOption 1: Do X."
        )

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify recommendation context was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert "Option 1: Do X" in context["prior_analysis_section"]
        assert "## Prior Investigation" not in context["prior_analysis_section"]

        # Verify info log was emitted for missing investigation
        assert any(
            "No investigation comment found" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )

    def test_execute_without_prior_analysis(self, mocker, caplog):
        """Test that fix works without any prior analysis."""
        import logging
        caplog.set_level(logging.INFO)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.description = "Description here"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_jira.get_investigation_comment.return_value = None
        mock_jira.get_recommendation_comment.return_value = None

        mock_github = MagicMock()
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_github.create_pull_request.return_value = mock_pr

        mock_result = ClaudeResult(
            content="Fixed the bug by...",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = FixAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify empty prior analysis section was passed
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        context = call_kwargs["context"]
        assert context["prior_analysis_section"] == ""

        # Verify info logs were emitted for both missing
        assert any(
            "No investigation comment found" in record.message
            for record in caplog.records
        )
        assert any(
            "No recommendation comment found" in record.message
            for record in caplog.records
        )
