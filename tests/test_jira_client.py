import pytest
from unittest.mock import Mock, MagicMock
from alm_orchestrator.jira_client import JiraClient
from alm_orchestrator.config import Config


@pytest.fixture
def mock_config():
    return Config(
        jira_url="https://test.atlassian.net",
        jira_user="test@example.com",
        jira_api_token="test-token",
        jira_project_key="TEST",
        github_token="ghp_test",
        github_repo="owner/repo",
        anthropic_api_key="sk-ant-test",
    )


class TestJiraClient:
    def test_initialization(self, mock_config, mocker):
        mock_jira_class = mocker.patch("alm_orchestrator.jira_client.JIRA")

        client = JiraClient(mock_config)

        mock_jira_class.assert_called_once_with(
            server="https://test.atlassian.net",
            basic_auth=("test@example.com", "test-token"),
        )

    def test_fetch_issues_with_ai_labels(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)

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
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)

        mock_issue = MagicMock()
        mock_issue.fields.labels = ["ai-investigate", "ai-impact", "bug", "priority-high"]

        client = JiraClient(mock_config)
        ai_labels = client.get_ai_labels(mock_issue)

        assert ai_labels == ["ai-impact", "ai-investigate"]
        assert "bug" not in ai_labels

    def test_ai_label_constants(self, mock_config, mocker):
        mocker.patch("alm_orchestrator.jira_client.JIRA")
        client = JiraClient(mock_config)

        assert "ai-investigate" in client.AI_LABELS
        assert "ai-impact" in client.AI_LABELS
        assert "ai-recommend" in client.AI_LABELS
        assert "ai-fix" in client.AI_LABELS
        assert "ai-implement" in client.AI_LABELS
        assert "ai-code-review" in client.AI_LABELS
        assert "ai-security-review" in client.AI_LABELS


class TestJiraClientUpdates:
    def test_add_label(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)

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

        client = JiraClient(mock_config)
        client.add_comment("TEST-123", "AI analysis complete:\n\nRoot cause identified.")

        mock_jira.add_comment.assert_called_once_with(
            "TEST-123",
            "AI analysis complete:\n\nRoot cause identified."
        )

    def test_remove_label(self, mock_config, mocker):
        mock_jira = MagicMock()
        mocker.patch("alm_orchestrator.jira_client.JIRA", return_value=mock_jira)

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

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.labels = ["bug"]
        mock_jira.issue.return_value = mock_issue

        client = JiraClient(mock_config)
        # Should not raise, just no-op
        client.remove_label("TEST-123", "ai-investigate")

        mock_issue.update.assert_not_called()
