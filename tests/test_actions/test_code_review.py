"""Tests for code review action handler."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.code_review import CodeReviewAction
from alm_orchestrator.claude_executor import ClaudeResult


class TestCodeReviewAction:
    def test_label_property(self):
        action = CodeReviewAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        assert action.label == "ai-code-review"

    def test_allowed_issue_types(self):
        action = CodeReviewAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        assert action.allowed_issue_types == ["Bug", "Story"]

    def test_execute_rejects_invalid_issue_type(self):
        """Execute returns early for non-Bug/Story issue types."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.issuetype.name = "Task"
        mock_issue.fields.description = "Test description"

        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_claude = MagicMock()

        action = CodeReviewAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        mock_github.clone_repo.assert_not_called()
        mock_claude.execute_with_template.assert_not_called()
        mock_jira.add_comment.assert_called_once()
        assert "INVALID ISSUE TYPE" in mock_jira.add_comment.call_args[0][1]
        assert "Rejected" in result

    def test_execute_reviews_pr(self, mocker):
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Review fix for orphaned recipes"
        mock_issue.fields.description = "PR: https://github.com/owner/repo/pull/42"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_jira.get_comments.return_value = []

        mock_github = MagicMock()
        mock_github.get_pr_info.return_value = {
            "head_branch": "feature/fix-recipes",
            "base_branch": "main",
            "changed_files": ["src/recipes.py", "tests/test_recipes.py"],
            "title": "Fix orphaned recipes bug",
            "body": "This PR fixes the bug where recipes become orphaned.",
        }
        mock_github.clone_repo.return_value = "/tmp/work-dir"

        mock_result = ClaudeResult(
            content="## Code Review\n\nApproved with minor suggestions.",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        mock_claude = MagicMock()
        mock_claude.execute_with_template.return_value = mock_result

        action = CodeReviewAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Verify PR info was fetched
        mock_github.get_pr_info.assert_called_once_with(42)

        # Verify repo was cloned with PR's head branch
        mock_github.clone_repo.assert_called_once_with(branch="feature/fix-recipes")

        # Verify Claude was invoked with correct action and changed files
        mock_claude.execute_with_template.assert_called_once()
        call_kwargs = mock_claude.execute_with_template.call_args[1]
        assert call_kwargs["action"] == "code_review"
        assert "src/recipes.py" in call_kwargs["context"]["changed_files"]
        assert "tests/test_recipes.py" in call_kwargs["context"]["changed_files"]

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
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()
        mock_jira.get_comments.return_value = []
        mock_github = MagicMock()
        mock_claude = MagicMock()

        action = CodeReviewAction(prompts_dir="/tmp/prompts", validator=MagicMock())
        result = action.execute(mock_issue, mock_jira, mock_github, mock_claude)

        # Should post error comment and remove label
        mock_jira.add_comment.assert_called_once()
        comment = mock_jira.add_comment.call_args[0][1]
        assert "Could not find PR" in comment

        mock_jira.remove_label.assert_called_with("TEST-123", "ai-code-review")

        # Should NOT clone or invoke Claude
        mock_github.clone_repo.assert_not_called()
        mock_claude.execute_with_template.assert_not_called()


class TestCodeReviewPRInComments:
    """Tests for finding PR in comments."""

    @pytest.fixture
    def action(self):
        return CodeReviewAction(prompts_dir="/tmp/prompts", validator=MagicMock())

    @pytest.fixture
    def mock_issue(self):
        issue = MagicMock()
        issue.key = "TEST-123"
        issue.fields.description = "No PR in description"
        issue.fields.issuetype.name = "Bug"
        return issue

    @pytest.fixture
    def mock_jira_client(self):
        return MagicMock()

    @pytest.fixture
    def mock_github_client(self):
        client = MagicMock()
        client.get_pr_info.return_value = {
            "head_branch": "feature/test-branch",
            "base_branch": "main",
            "changed_files": ["src/test.py"],
            "title": "Test PR",
            "body": "Test PR description",
        }
        client.clone_repo.return_value = "/tmp/workdir"
        return client

    @pytest.fixture
    def mock_claude_executor(self):
        executor = MagicMock()
        executor.execute_with_template.return_value = ClaudeResult(
            content="Review content",
            cost_usd=0.05,
            duration_ms=5000,
            session_id="test-session"
        )
        return executor

    def test_finds_pr_in_comments_when_not_in_description(
        self, action, mock_issue, mock_jira_client, mock_github_client, mock_claude_executor
    ):
        """Test that action finds PR in comments when description has none."""
        mock_jira_client.get_comments.return_value = [{"body": "PR #42", "author_id": "user-1", "created": "2024-01-01T10:00:00"}]

        result = action.execute(mock_issue, mock_jira_client, mock_github_client, mock_claude_executor)

        assert "PR #42" in result
        mock_github_client.add_pr_comment.assert_called_once()
        call_args = mock_github_client.add_pr_comment.call_args
        assert call_args[0][0] == 42  # PR number

    def test_description_pr_takes_priority_over_comments(
        self, action, mock_issue, mock_jira_client, mock_github_client, mock_claude_executor
    ):
        """Test that PR in description is used even when comments have different PR."""
        mock_issue.fields.description = "PR #1"
        mock_jira_client.get_comments.return_value = [{"body": "PR #99", "author_id": "user-1", "created": "2024-01-01T10:00:00"}]

        result = action.execute(mock_issue, mock_jira_client, mock_github_client, mock_claude_executor)

        call_args = mock_github_client.add_pr_comment.call_args
        assert call_args[0][0] == 1  # PR from description, not comments

    def test_error_message_mentions_comments(
        self, action, mock_issue, mock_jira_client, mock_github_client, mock_claude_executor
    ):
        """Test that error message tells user to check description or comments."""
        mock_jira_client.get_comments.return_value = []

        action.execute(mock_issue, mock_jira_client, mock_github_client, mock_claude_executor)

        call_args = mock_jira_client.add_comment.call_args
        error_message = call_args[0][1]
        assert "comments" in error_message.lower()
