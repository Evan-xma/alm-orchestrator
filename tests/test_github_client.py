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


class TestGitHubClientPR:
    def test_create_pull_request(self, mock_config, mocker):
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.html_url = "https://github.com/acme-corp/recipe-api/pull/42"
        mock_repo.create_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo
        mocker.patch("alm_orchestrator.github_client.Github", return_value=mock_github)

        client = GitHubClient(mock_config)
        pr = client.create_pull_request(
            branch="ai/fix-TEST-123",
            title="fix: resolve orphaned recipes issue",
            body="This PR fixes the orphaned recipes bug.\n\nJira: TEST-123"
        )

        assert pr.number == 42
        mock_repo.create_pull.assert_called_once_with(
            title="fix: resolve orphaned recipes issue",
            body="This PR fixes the orphaned recipes bug.\n\nJira: TEST-123",
            head="ai/fix-TEST-123",
            base="main"
        )

    def test_add_pr_comment(self, mock_config, mocker):
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_repo.get_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo
        mocker.patch("alm_orchestrator.github_client.Github", return_value=mock_github)

        client = GitHubClient(mock_config)
        client.add_pr_comment(42, "## Code Review\n\nLooks good!")

        mock_repo.get_pull.assert_called_once_with(42)
        mock_pr.create_issue_comment.assert_called_once_with("## Code Review\n\nLooks good!")

    def test_get_pr_by_branch(self, mock_config, mocker):
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.head.ref = "ai/fix-TEST-123"
        mock_repo.get_pulls.return_value = [mock_pr]
        mock_github.get_repo.return_value = mock_repo
        mocker.patch("alm_orchestrator.github_client.Github", return_value=mock_github)

        client = GitHubClient(mock_config)
        pr = client.get_pr_by_branch("ai/fix-TEST-123")

        assert pr is not None
        assert pr.number == 42

    def test_get_pr_by_branch_not_found(self, mock_config, mocker):
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_pulls.return_value = []
        mock_github.get_repo.return_value = mock_repo
        mocker.patch("alm_orchestrator.github_client.Github", return_value=mock_github)

        client = GitHubClient(mock_config)
        pr = client.get_pr_by_branch("nonexistent-branch")

        assert pr is None
