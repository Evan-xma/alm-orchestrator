"""GitHub API client for the ALM Orchestrator."""

import shutil
import subprocess
import tempfile
from github import Github
from alm_orchestrator.config import Config


class GitHubClient:
    """Client for interacting with GitHub API and git operations."""

    def __init__(self, config: Config):
        """Initialize GitHub client with configuration.

        Args:
            config: Application configuration containing GitHub credentials.
        """
        self._config = config
        self._github = Github(config.github_token)
        self._repo = self._github.get_repo(config.github_repo)

    def get_authenticated_clone_url(self) -> str:
        """Get clone URL with embedded auth token.

        Returns:
            HTTPS clone URL with token for authentication.
        """
        return f"https://{self._config.github_token}@github.com/{self._config.github_repo}.git"

    def clone_repo(self, branch: str = "main") -> str:
        """Clone the repository to a temporary directory.

        Args:
            branch: Branch to clone. Defaults to "main".

        Returns:
            Path to the cloned repository working directory.

        Raises:
            subprocess.CalledProcessError: If git clone fails.
        """
        work_dir = tempfile.mkdtemp(prefix="alm-orchestrator-")
        clone_url = self.get_authenticated_clone_url()

        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, clone_url, work_dir],
            check=True,
            capture_output=True,
        )

        return work_dir

    def create_branch(self, work_dir: str, branch_name: str) -> None:
        """Create and checkout a new branch.

        Args:
            work_dir: Path to the git repository.
            branch_name: Name of the branch to create.

        Raises:
            subprocess.CalledProcessError: If git checkout fails.
        """
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

    def commit_and_push(self, work_dir: str, branch: str, message: str) -> None:
        """Stage all changes, commit, and push to remote.

        Args:
            work_dir: Path to the git repository.
            branch: Branch name to push.
            message: Commit message.

        Raises:
            subprocess.CalledProcessError: If any git command fails.
        """
        subprocess.run(
            ["git", "add", "-A"],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

    def cleanup(self, work_dir: str) -> None:
        """Remove the temporary working directory.

        Args:
            work_dir: Path to remove.
        """
        shutil.rmtree(work_dir, ignore_errors=True)
