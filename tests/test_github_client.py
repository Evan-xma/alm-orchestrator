import os
import tempfile
import pytest
from unittest.mock import MagicMock
from alm_orchestrator.github_client import GitHubClient
from alm_orchestrator.config import Config


@pytest.fixture
def mock_config():
    return Config(
        jira_url="https://test.atlassian.net",
        jira_user="test@example.com",
        jira_api_token="test-token",
        jira_project_key="TEST",
        github_token="ghp_test",
        github_repo="acme-corp/recipe-api",
        anthropic_api_key="sk-ant-test",
    )


class TestGitHubClient:
    def test_initialization(self, mock_config, mocker):
        mock_github_class = mocker.patch("alm_orchestrator.github_client.Github")

        client = GitHubClient(mock_config)

        mock_github_class.assert_called_once_with("ghp_test")

    def test_clone_url_construction(self, mock_config, mocker):
        mocker.patch("alm_orchestrator.github_client.Github")

        client = GitHubClient(mock_config)
        clone_url = client.get_authenticated_clone_url()

        assert clone_url == "https://ghp_test@github.com/acme-corp/recipe-api.git"

    def test_clone_repo_creates_temp_directory(self, mock_config, mocker):
        mocker.patch("alm_orchestrator.github_client.Github")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        client = GitHubClient(mock_config)
        work_dir = client.clone_repo()

        assert work_dir is not None
        assert os.path.isabs(work_dir)

        # Verify git clone was called
        mock_run.assert_called()
        clone_call = mock_run.call_args_list[0]
        assert "git" in clone_call[0][0]
        assert "clone" in clone_call[0][0]

    def test_create_branch(self, mock_config, mocker):
        mocker.patch("alm_orchestrator.github_client.Github")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        client = GitHubClient(mock_config)
        client.create_branch("/tmp/test-repo", "ai/fix-TEST-123")

        # Should run git checkout -b
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("checkout" in c and "-b" in c for c in calls)

    def test_commit_and_push(self, mock_config, mocker):
        mocker.patch("alm_orchestrator.github_client.Github")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        client = GitHubClient(mock_config)
        client.commit_and_push(
            work_dir="/tmp/test-repo",
            branch="ai/fix-TEST-123",
            message="fix: resolve orphaned recipes issue"
        )

        calls = [str(c) for c in mock_run.call_args_list]
        assert any("add" in c for c in calls)
        assert any("commit" in c for c in calls)
        assert any("push" in c for c in calls)

    def test_cleanup_work_dir(self, mock_config, mocker):
        mocker.patch("alm_orchestrator.github_client.Github")
        mock_rmtree = mocker.patch("shutil.rmtree")

        client = GitHubClient(mock_config)
        client.cleanup("/tmp/some-temp-dir")

        mock_rmtree.assert_called_once_with("/tmp/some-temp-dir", ignore_errors=True)
