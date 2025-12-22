"""Tests for main daemon loop."""

import pytest
from unittest.mock import MagicMock, patch
from alm_orchestrator.daemon import Daemon
from alm_orchestrator.config import Config
from alm_orchestrator.output_validator import OutputValidator


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
        poll_interval_seconds=1,
    )


class TestDaemon:
    def test_initialization(self, mock_config, mocker):
        mocker.patch("alm_orchestrator.daemon.JiraClient")
        mocker.patch("alm_orchestrator.daemon.GitHubClient")
        mocker.patch("alm_orchestrator.daemon.ClaudeExecutor")
        mocker.patch("alm_orchestrator.daemon.discover_actions")

        daemon = Daemon(mock_config, prompts_dir="/tmp/prompts")

        assert daemon is not None
        assert daemon._running is False

    def test_single_poll_processes_issues(self, mock_config, mocker):
        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_claude = MagicMock()

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.labels = ["ai-investigate"]
        mock_jira.fetch_issues_with_ai_labels.return_value = [mock_issue]
        mock_jira.get_ai_labels.return_value = ["ai-investigate"]

        mocker.patch("alm_orchestrator.daemon.JiraClient", return_value=mock_jira)
        mocker.patch("alm_orchestrator.daemon.GitHubClient", return_value=mock_github)
        mocker.patch("alm_orchestrator.daemon.ClaudeExecutor", return_value=mock_claude)

        mock_action = MagicMock()
        mock_router = MagicMock()
        mock_router.has_action.return_value = True
        mock_router.get_action.return_value = mock_action
        mocker.patch("alm_orchestrator.daemon.discover_actions", return_value=mock_router)

        daemon = Daemon(mock_config, prompts_dir="/tmp/prompts")
        processed = daemon.poll_once()

        # Verify action was executed
        mock_action.execute.assert_called_once()
        assert processed == 1

    def test_poll_removes_original_label_and_adds_processing_label(self, mock_config, mocker):
        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_claude = MagicMock()

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_jira.fetch_issues_with_ai_labels.return_value = [mock_issue]
        mock_jira.get_ai_labels.return_value = ["ai-investigate"]

        mock_jira_class = mocker.patch("alm_orchestrator.daemon.JiraClient", return_value=mock_jira)
        mock_jira_class.PROCESSING_LABEL = "ai-processing"
        mocker.patch("alm_orchestrator.daemon.GitHubClient", return_value=mock_github)
        mocker.patch("alm_orchestrator.daemon.ClaudeExecutor", return_value=mock_claude)

        mock_router = MagicMock()
        mock_router.has_action.return_value = True
        mocker.patch("alm_orchestrator.daemon.discover_actions", return_value=mock_router)

        daemon = Daemon(mock_config, prompts_dir="/tmp/prompts")
        daemon.poll_once()

        # Verify original label removed, processing label added, then processing label removed
        remove_calls = mock_jira.remove_label.call_args_list
        assert len(remove_calls) == 2
        assert remove_calls[0] == mocker.call("TEST-123", "ai-investigate")
        assert remove_calls[1] == mocker.call("TEST-123", "ai-processing")
        mock_jira.add_label.assert_called_once_with("TEST-123", "ai-processing")

    def test_poll_handles_action_error(self, mock_config, mocker):
        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_claude = MagicMock()

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_jira.fetch_issues_with_ai_labels.return_value = [mock_issue]
        mock_jira.get_ai_labels.return_value = ["ai-investigate"]

        mock_jira_class = mocker.patch("alm_orchestrator.daemon.JiraClient", return_value=mock_jira)
        mock_jira_class.PROCESSING_LABEL = "ai-processing"
        mocker.patch("alm_orchestrator.daemon.GitHubClient", return_value=mock_github)
        mocker.patch("alm_orchestrator.daemon.ClaudeExecutor", return_value=mock_claude)

        mock_action = MagicMock()
        mock_action.execute.side_effect = Exception("Action failed")
        mock_router = MagicMock()
        mock_router.has_action.return_value = True
        mock_router.get_action.return_value = mock_action
        mocker.patch("alm_orchestrator.daemon.discover_actions", return_value=mock_router)

        daemon = Daemon(mock_config, prompts_dir="/tmp/prompts")
        processed = daemon.poll_once()

        # Should post error comment
        mock_jira.add_comment.assert_called()
        comment = mock_jira.add_comment.call_args[0][1]
        assert "FAILED" in comment.upper()
        assert "ai-investigate" in comment

        # Original label removed upfront, processing label removed in finally
        remove_calls = mock_jira.remove_label.call_args_list
        assert len(remove_calls) == 2
        assert remove_calls[0] == mocker.call("TEST-123", "ai-investigate")
        assert remove_calls[1] == mocker.call("TEST-123", "ai-processing")

    def test_run_can_be_stopped(self, mock_config, mocker):
        mock_jira = MagicMock()
        mock_jira.fetch_issues_with_ai_labels.return_value = []

        mocker.patch("alm_orchestrator.daemon.JiraClient", return_value=mock_jira)
        mocker.patch("alm_orchestrator.daemon.GitHubClient")
        mocker.patch("alm_orchestrator.daemon.ClaudeExecutor")
        mocker.patch("alm_orchestrator.daemon.discover_actions")

        daemon = Daemon(mock_config, prompts_dir="/tmp/prompts")

        # Simulate stopping after first poll
        def stop_after_poll(*args):
            daemon.stop()

        mock_jira.fetch_issues_with_ai_labels.side_effect = stop_after_poll

        daemon.run()

        assert daemon._running is False


class TestDaemonValidatorIntegration:
    def test_daemon_creates_validator(self):
        """Daemon instantiates OutputValidator on init."""
        config = MagicMock()
        config.claude_timeout_seconds = 600

        with patch('alm_orchestrator.daemon.JiraClient'), \
             patch('alm_orchestrator.daemon.GitHubClient'), \
             patch('alm_orchestrator.daemon.ClaudeExecutor'), \
             patch('alm_orchestrator.daemon.discover_actions') as mock_discover:

            mock_router = MagicMock()
            mock_router.action_count = 1
            mock_router.action_names = ["TestAction"]
            mock_discover.return_value = mock_router

            daemon = Daemon(config, prompts_dir="/tmp/prompts")

            # Verify validator was created and passed to discover_actions
            mock_discover.assert_called_once()
            call_kwargs = mock_discover.call_args[1]
            assert 'validator' in call_kwargs
            assert isinstance(call_kwargs['validator'], OutputValidator)
