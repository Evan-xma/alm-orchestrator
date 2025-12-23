import os
import tempfile
import pytest
from unittest.mock import MagicMock
from alm_orchestrator.github_client import GitHubClient, generate_branch_name
from alm_orchestrator.config import Config


@pytest.fixture
def mock_config():
    return Config(
        jira_url="https://test.atlassian.net",
        jira_project_key="TEST",
        github_token="ghp_test",
        github_repo="acme-corp/recipe-api",
        jira_client_id="test-client-id",
        jira_client_secret="test-client-secret",
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
            message="fix: resolve orphaned recipes issue",
            issue_key="TEST-123",
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

    def test_get_pr_info(self, mock_config, mocker):
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.head.ref = "feature/add-user-auth"
        mock_pr.base.ref = "main"
        mock_pr.title = "Add user authentication"
        mock_pr.body = "This PR adds OAuth2 authentication to the API."

        mock_file1 = MagicMock()
        mock_file1.filename = "src/auth.py"
        mock_file2 = MagicMock()
        mock_file2.filename = "tests/test_auth.py"
        mock_pr.get_files.return_value = [mock_file1, mock_file2]

        mock_repo.get_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo
        mocker.patch("alm_orchestrator.github_client.Github", return_value=mock_github)

        client = GitHubClient(mock_config)
        pr_info = client.get_pr_info(42)

        assert pr_info["head_branch"] == "feature/add-user-auth"
        assert pr_info["base_branch"] == "main"
        assert pr_info["changed_files"] == ["src/auth.py", "tests/test_auth.py"]
        assert pr_info["title"] == "Add user authentication"
        assert pr_info["body"] == "This PR adds OAuth2 authentication to the API."
        mock_repo.get_pull.assert_called_once_with(42)


class TestGenerateBranchName:
    def test_generates_timestamped_branch_name(self):
        """Branch name includes prefix, issue key, and timestamp."""
        branch = generate_branch_name("fix-", "RCPAPI-1")

        assert branch.startswith("fix-rcpapi-1-")
        # Should have format: fix-rcpapi-1-YYYYMMDD-HHMM
        parts = branch.split("-")
        assert len(parts) == 5  # fix, rcpapi, 1, YYYYMMDD, HHMM
        assert len(parts[3]) == 8  # YYYYMMDD
        assert len(parts[4]) == 4  # HHMM

    def test_lowercases_issue_key(self):
        """Issue key is lowercased in branch name."""
        branch = generate_branch_name("feature-", "TEST-123")

        assert "test-123" in branch
        assert "TEST-123" not in branch

    def test_different_prefixes(self):
        """Works with different branch prefixes."""
        fix_branch = generate_branch_name("fix-", "BUG-1")
        feat_branch = generate_branch_name("feature-", "STORY-1")

        assert fix_branch.startswith("fix-bug-1-")
        assert feat_branch.startswith("feature-story-1-")
