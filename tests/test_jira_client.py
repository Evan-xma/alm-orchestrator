import pytest
from unittest.mock import Mock, MagicMock, patch
from alm_orchestrator.jira_client import JiraClient, OAuthTokenManager
from alm_orchestrator.config import Config


@pytest.fixture
def mock_config():
    return Config(
        jira_url="https://test.atlassian.net",
        jira_project_key="TEST",
        github_token="ghp_test",
        github_repo="owner/repo",
        jira_client_id="test-client-id",
        jira_client_secret="test-client-secret",
        anthropic_api_key="sk-ant-test",
    )


class TestJiraClient:
    def test_initialization(self, mock_config, mocker):
        mock_jira_class = mocker.patch("alm_orchestrator.jira_client.JIRA")
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        client = JiraClient(mock_config)
        # Trigger lazy initialization
        client._get_jira()

        mock_jira_class.assert_called_once_with(
            server="https://api.atlassian.com/ex/jira/mock-cloud-id",
            token_auth="mock-access-token",
        )

    def test_fetch_issues_with_ai_labels(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Fix the bug"
        mock_issue.fields.labels = ["ai-investigate", "bug"]
        mock_jira.search_issues.return_value = [mock_issue]

        client = JiraClient(mock_config)
        issues = client.fetch_issues_with_ai_labels()

        assert len(issues) == 1
        assert issues[0].key == "TEST-123"

        # Verify JQL query includes AI labels
        call_args = mock_jira.search_issues.call_args
        jql = call_args[0][0]
        assert "ai-investigate" in jql or "labels in" in jql

    def test_get_ai_labels_for_issue(self, mock_config, mocker):
        mock_jira = MagicMock()
        mock_myself = MagicMock()
        mock_myself.__getitem__ = lambda self, key: "mock-account-id" if key == "accountId" else None
        mock_jira.myself.return_value = mock_myself
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        mock_issue = MagicMock()
        mock_issue.fields.labels = ["ai-investigate", "ai-impact", "bug", "priority-high"]

        client = JiraClient(mock_config)
        ai_labels = client.get_ai_labels(mock_issue)

        assert ai_labels == ["ai-impact", "ai-investigate"]
        assert "bug" not in ai_labels

    def test_ai_label_constants(self, mock_config, mocker):
        mock_jira = MagicMock()
        mock_myself = MagicMock()
        mock_myself.__getitem__ = lambda self, key: "mock-account-id" if key == "accountId" else None
        mock_jira.myself.return_value = mock_myself
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")
        client = JiraClient(mock_config)

        assert "ai-investigate" in client.AI_LABELS
        assert "ai-impact" in client.AI_LABELS
        assert "ai-recommend" in client.AI_LABELS
        assert "ai-fix" in client.AI_LABELS
        assert "ai-implement" in client.AI_LABELS
        assert "ai-code-review" in client.AI_LABELS
        assert "ai-security-review" in client.AI_LABELS

    def test_account_id_fetched_at_init(self, mock_config, mocker):
        """Test that account_id is fetched at initialization."""
        mock_jira = MagicMock()
        mock_myself = MagicMock()
        mock_myself.__getitem__ = lambda self, key: "abc123-account-id" if key == "accountId" else None
        mock_jira.myself.return_value = mock_myself
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        client = JiraClient(mock_config)

        assert client.account_id == "abc123-account-id"
        mock_jira.myself.assert_called_once()


class TestJiraClientUpdates:
    def test_add_label(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.labels = ["bug"]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        client.add_label("TEST-123", "ai-processing")

        mock_issue.update.assert_called_once()
        update_call = mock_issue.update.call_args
        new_labels = update_call[1]["fields"]["labels"]
        assert "ai-processing" in new_labels
        assert "bug" in new_labels

    def test_add_comment(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        client = JiraClient(mock_config)
        client.add_comment("TEST-123", "AI analysis complete:\n\nRoot cause identified.")

        mock_jira.add_comment.assert_called_once_with(
            "TEST-123",
            "AI analysis complete:\n\nRoot cause identified."
        )

    def test_remove_label(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.labels = ["ai-investigate", "bug", "priority-high"]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        client.remove_label("TEST-123", "ai-investigate")

        # Should update issue with label removed
        mock_issue.update.assert_called_once()
        update_call = mock_issue.update.call_args
        new_labels = update_call[1]["fields"]["labels"]
        assert "ai-investigate" not in new_labels
        assert "bug" in new_labels
        assert "priority-high" in new_labels

    def test_remove_label_not_present(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.labels = ["bug"]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        # Should not raise, just no-op
        client.remove_label("TEST-123", "ai-investigate")

        mock_issue.update.assert_not_called()


class TestJiraClientComments:
    """Tests for comment-related methods."""

    def test_get_comments_returns_bodies_newest_first(self, mock_config, mocker):
        """Test that get_comments returns comment bodies sorted newest-first."""
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        # Create mock comments with created timestamps
        mock_comment_1 = MagicMock()
        mock_comment_1.body = "First comment"
        mock_comment_1.created = "2024-01-01T10:00:00.000+0000"

        mock_comment_2 = MagicMock()
        mock_comment_2.body = "Second comment"
        mock_comment_2.created = "2024-01-02T10:00:00.000+0000"

        mock_comment_3 = MagicMock()
        mock_comment_3.body = "Third comment"
        mock_comment_3.created = "2024-01-03T10:00:00.000+0000"

        # Mock issue with comments in arbitrary order
        mock_issue = MagicMock()
        mock_issue.fields.comment.comments = [mock_comment_2, mock_comment_1, mock_comment_3]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        result = client.get_comments("TEST-123")

        # Should be sorted newest-first
        assert result == ["Third comment", "Second comment", "First comment"]
        mock_jira.issue.assert_called_once_with("TEST-123", fields="comment")

    def test_get_comments_returns_empty_list_when_no_comments(self, mock_config, mocker):
        """Test that get_comments returns empty list when issue has no comments."""
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)
        mocker.patch.object(OAuthTokenManager, "get_token", return_value="mock-access-token")
        mocker.patch.object(OAuthTokenManager, "get_api_url", return_value="https://api.atlassian.com/ex/jira/mock-cloud-id")

        mock_issue = MagicMock()
        mock_issue.fields.comment.comments = []
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        result = client.get_comments("TEST-123")

        assert result == []
